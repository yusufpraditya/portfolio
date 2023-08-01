import argparse
import numpy as np
import cv2 as cv
import os
import pickle
from serial.tools.list_ports import comports
import serial
import time

tm = cv.TickMeter()
database = {}

cosine_similarity_threshold = 0.463
l2_similarity_threshold = 1.0

faces = os.getcwd() + '/faces/'
faces_name = []
for path in os.listdir(faces):
    faces_name.append(path)

ser = []

global connected
connected = False

parser = argparse.ArgumentParser()
parser.add_argument('--scale', '-sc', type=float, default=1.0, help='Scale factor used to resize input video frames.')
parser.add_argument('--face_detection_model', '-fd', type=str, default='face_detection_yunet.onnx', help='Path to the face detection model. Download the model at https://github.com/opencv/opencv_zoo/tree/master/models/face_detection_yunet')
parser.add_argument('--face_recognition_model', '-fr', type=str, default='face_recognition_sface.onnx', help='Path to the face recognition model. Download the model at https://github.com/opencv/opencv_zoo/tree/master/models/face_recognition_sface')
parser.add_argument('--score_threshold', type=float, default=0.9, help='Filtering out faces of score < score_threshold.')
parser.add_argument('--nms_threshold', type=float, default=0.3, help='Suppress bounding boxes of iou >= nms_threshold.')
parser.add_argument('--top_k', type=int, default=5000, help='Keep top_k bounding boxes before NMS.')
args = parser.parse_args()

def mode(array):
    if array == []:
        return 'unknown'
    most = max(list(map(array.count, array)))
    list_mode = list(set(filter(lambda x: array.count(x) == most, array)))
    if len(list_mode) > 1:
        return 'unknown'
    else:
        return list_mode[0]

def cam_index():
    webcam_index = 0
    arr_webcam = []
    while True:        
        c = cv.VideoCapture(webcam_index)
        
        if not c.read()[0]:
            webcam_index += 1
            if webcam_index == 11:
                webcam_index = 0
        else:
            arr_webcam.append(webcam_index)
            break
        c.release()
    print("Cam Index: " + str(arr_webcam))
    return arr_webcam

def connect():      
    ser.clear()
    ports_name = []
    ports = [p.name for p in comports()]
    print("len ports: " + str(len(ports)))
    for i in range(len(ports)):
        if len(ports) > 0:
            if "USB" in ports[i] or "ACM" in ports[i]:
                print(ports[i])
                ports_name.append("/dev/" + ports[i])
                print(ports_name)
                ser.append(serial.Serial(ports_name[i], timeout=0))
                print(ser)    

def find_face(input, faces, thickness=2):      
    face_img = input.copy()   
    for idx, face in enumerate(faces[1]):
        coords = face[:-1].astype(np.int32)
        for i in range(len(coords)):
            if coords[i] < 0:
                coords[i] = 0
        cv.rectangle(input, (coords[0], coords[1]), (coords[0]+coords[2], coords[1]+coords[3]), (0, 255, 0), thickness)
        face_img = face_img[coords[1]:coords[1] + coords[3], coords[0]:coords[0] + coords[2]]                
        if len(face_img) != 0:                
            return face_img    

def write_serial(identity):
    if ser == []:
        connect()
    print(ser)
    try:
        if identity == "unknown":            
            for i in range(len(ser)):
                print("unknown...")
                ser[i].write(str.encode("0\n"))
        else:        
            for i in range(len(ser)):
                print("written to serial...")                
                ser[i].write(str.encode("1\n"))
    except:
        connect()          

def recognize(face_img, database):
    recognizer = cv.FaceRecognizerSF.create(args.face_recognition_model,"")        
    face_feature = recognizer.feature(face_img)
    
    max_cosine = 0
    min_l2 = 2
    identity = 'unknown'
    for key, value in database.items():
        cosine_score = recognizer.match(face_feature, value, cv.FaceRecognizerSF_FR_COSINE)
        l2_score = recognizer.match(face_feature, value, cv.FaceRecognizerSF_FR_NORM_L2)
        if cosine_score > max_cosine or l2_score < min_l2:
            max_cosine = cosine_score
            min_l2 = l2_score
            identity = key
    if max_cosine >= cosine_similarity_threshold or min_l2 <= l2_similarity_threshold:
        identity = identity
    else:
        identity = 'unknown'

    for dirpath, dirname, filename in os.walk(faces):            
        if identity+".jpg" in filename:
            identity = dirpath.split("/")[-1]
    return identity, min_l2, max_cosine

def setup():
    for face in faces_name:
        image_folder = faces + face + "/"
        
        for image in os.listdir(image_folder):
            image_path = image_folder + image
            print(image_path)
            try:
                img = cv.imread(image_path)
                recognizer = cv.FaceRecognizerSF.create(args.face_recognition_model,"")
                face_feature = recognizer.feature(img)
                database[os.path.splitext(image)[0]] = face_feature
                myfile = open("data.pkl", "wb")
                pickle.dump(database, myfile)
                myfile.close()
            except:
                print('error')
    print("DONE SETUP")

def loop():
    face_detected = 0
    start_time = time.time()
    write_count = 0
    arr_identity = []
    myfile = open("data.pkl", "rb")
    database = pickle.load(myfile)
    myfile.close()    

    yunet = cv.FaceDetectorYN.create(
        model=args.face_detection_model,
        config='',
        input_size=(320, 320),
        score_threshold=args.score_threshold,
        nms_threshold=args.nms_threshold,
        top_k=args.top_k        
    )

    webcam_index = cam_index()    
    cap = cv.VideoCapture(webcam_index[0])
    scale_percent = 30
    frame_w = int(int(cap.get(cv.CAP_PROP_FRAME_WIDTH)) * scale_percent / 100)
    frame_h = int(int(cap.get(cv.CAP_PROP_FRAME_HEIGHT)) * scale_percent / 100)    
    
    dim = (frame_w, frame_h)
    while cv.waitKey(1) < 0:        
        tm.start()        
        has_frame, img = cap.read()
        if has_frame:
            img = cv.resize(img, dim)
            height, width, ch = img.shape
            yunet.setInputSize([width, height])
            yunet_detect = yunet.detect(img)  
            if yunet_detect[1] is not None:
                face_detected += 1                 
                face_img = find_face(img, yunet_detect)
                
                identity, l2_score, cosine_score = recognize(face_img, database) 
                arr_identity.append(identity)

                print("face name: ", identity)    
                print("l2 score: ", l2_score)
                print("cosine score: ", cosine_score)
                print(" ")
            else:
                face_detected = 0
                start_time = time.time()
                arr_identity.clear()
            print("face detected count: " + str(face_detected))
            if face_detected > 14:
                                
                identity = mode(arr_identity) 
                mean_identity = arr_identity.count(identity) / len(arr_identity)
                if mean_identity < 0.7:
                    identity = 'unknown'
                elapsed_time = time.time() - start_time
                print(arr_identity, identity, mean_identity, elapsed_time)
                if write_count == 0:
                    print(write_count)
                    write_serial(identity)                
                arr_identity.clear()
                write_count += 1
                face_detected = 0
            else:
                write_count = 0            
            cv.imshow('frame', img)    
            tm.stop()

if __name__ == '__main__':   
    connect()
    setup()
    loop()

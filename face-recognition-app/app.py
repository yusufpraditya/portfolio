from PyQt6.QtWidgets import QMainWindow, QApplication, QFileDialog, QMessageBox, QWidget, QLabel, QGridLayout
from PyQt6 import uic, QtGui
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot, Qt
from PyQt6.QtMultimedia import *
from PyQt6.QtMultimediaWidgets import *
import cv2
import numpy as np
import sys
import os
import pickle
import datetime

class VideoThread(QThread):
    detection_signal = pyqtSignal(np.ndarray)
    crop_signal = pyqtSignal(np.ndarray)
    alignment_signal = pyqtSignal(np.ndarray)
    original_face_signal = pyqtSignal(np.ndarray)
    similar_face_signal = pyqtSignal(np.ndarray)
    stylesheet_signal = pyqtSignal(str)
    face_name_signal = pyqtSignal(str)
    error_signal = pyqtSignal() 
    
    def __init__(self, my_gui):
        super().__init__()
        self.isActive = True
        self.isStopped = False
        self.my_gui = my_gui
    
    def crop_face(self, original_img, face):
        face_img = original_img.copy()
        x, y, w, h = np.maximum(face[0:4].astype(np.int32), 0)
        face_img = face_img[y:y + h, x:x + w]               
        return face_img
    
    def align_face(self, original_img, face, model_sface):
        aligned_img = model_sface.alignCrop(original_img, face)
        return aligned_img

    def visualize(self, original_img, face):
        detected_img = original_img.copy()
        x, y, w, h = np.maximum(face[0:4].astype(np.int32), 0)
        start_point = (x, y)
        end_point = (x + w, y + h)
        rectangle_color = (0, 255, 0)
        cv2.rectangle(detected_img, start_point, end_point, rectangle_color, thickness=2)
        return detected_img

    def run(self):        
        global aligned_img           
        cap = cv2.VideoCapture(self.my_gui.cameraIndex, cv2.CAP_DSHOW)

        if self.my_gui.mode_videofoto_pengenalan or self.my_gui.mode_videofoto_registrasi:           
           cap = cv2.VideoCapture(self.my_gui.path_video)
           self.my_gui.panjang_frame_video = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        tm = cv2.TickMeter()

        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        model_yunet = cv2.FaceDetectorYN.create(
                    model=self.my_gui.file_model_deteksi,
                    config="",
                    input_size=(w, h),
                    score_threshold=0.7,
                    nms_threshold=0.3,
                    top_k=1)
        
        model_sface = cv2.FaceRecognizerSF.create(model=self.my_gui.file_model_pengenalan, config="")    
        
        white_background = '''
            background-color: #fff;
            color: #000;
        '''
        green_background = '''
            background-color: #00ff00;
            color: #000;
        '''
        red_background = '''
            background-color: #ff0000;
            color: #fff;
        '''

        while self.isActive:                        
            tm.start()            
            if self.my_gui.pause:
                cap.set(cv2.CAP_PROP_POS_FRAMES, self.my_gui.frame_video)
                self.my_gui.pause = False
            frame, original_img = cap.read()  
            self.my_gui.frame_video = cap.get(cv2.CAP_PROP_POS_FRAMES)
            if self.my_gui.mode_pengenalan:
                pickle_database = open(self.my_gui.lokasi_pickle, "rb")
                database = pickle.load(pickle_database)
                pickle_database.close()           
            
            try:
                face = model_yunet.detect(original_img)[1][0]
            except:
                face = None

            if self.isStopped:
                print("program stopped")
                self.my_gui.clear_all_labels()
                self.stylesheet_signal.emit(white_background)                
                self.my_gui.lcdSimilarity.display("0")   
                self.my_gui.lcdFPS.display("0")
                self.isStopped = False
                self.isActive = False
                break   

            if face is not None:
                detected_img = self.my_gui.visualize(original_img, face)
                face_img = self.my_gui.crop_face(original_img, face)
                aligned_img = self.my_gui.align_face(original_img, face, model_sface)
                face_feature = model_sface.feature(aligned_img)

                if self.my_gui.mode_pengenalan == False:
                    self.detection_signal.emit(detected_img)
                    self.crop_signal.emit(face_img)
                    self.alignment_signal.emit(aligned_img)
                else:
                    max_cosine = 0                    
                    if self.my_gui.btnSimilarity.text() == "Ganti":
                        cosine_similarity_threshold = float(self.my_gui.valSimilarity.text())
                    identity = 'unknown'
                    for key in database.keys():
                        name = key.split("_")[0]
                        if name != "img":
                            cosine_score = model_sface.match(face_feature, database[key])
                            if cosine_score > max_cosine:
                                max_cosine = cosine_score
                                identity = key
                    
                    str_max_cosine = "{:.3f}".format(round(max_cosine, 3))
                    self.my_gui.lcdSimilarity.display(str_max_cosine)                   
                    
                    if max_cosine >= cosine_similarity_threshold:
                        identity_image = database["img_" + identity]
                        self.similar_face_signal.emit(identity_image)
                        identity = identity.split("_")[0]                        
                        self.stylesheet_signal.emit(green_background)
                    else:
                        identity = 'unknown'
                        self.my_gui.clear_sf_label()
                        self.stylesheet_signal.emit(red_background)                   
                    
                    self.face_name_signal.emit(identity)

                    self.detection_signal.emit(detected_img)
                    self.crop_signal.emit(face_img)
                    self.alignment_signal.emit(aligned_img)
                    self.original_face_signal.emit(aligned_img)                                     
                    
            else:                 
                self.my_gui.clear_small_labels()                
                if frame:                    
                    self.detection_signal.emit(original_img)    
                else:
                    print("no frame")
                    self.my_gui.clear_all_labels()
                    if self.my_gui.mode_pengenalan:         
                        self.my_gui.tombol_stop_pengenalan()               
                        self.my_gui.refresh_cam_pengenalan()
                    else:                       
                        self.my_gui.tombol_stop() 
                        self.my_gui.refresh_cam_registrasi() 
                    self.error_signal.emit()
                    self.isStopped = True
                    break                  
            
            tm.stop()
            fps = "{:.2f}".format(round(tm.getFPS(), 2))
            self.my_gui.lcdFPS.display(fps)                          

    def stop(self):         
        self.quit()
        self.isActive = False
        self.my_gui.lcdSimilarity.display("0")
        self.my_gui.clear_all_labels()    

class WindowTentang(QWidget):
    def __init__(self):
        super().__init__()
        main_layout = QGridLayout()

        self.setWindowTitle("Tentang")

        img_dir = self.resource_path("assets") 
        img_file = os.path.join(img_dir, "tentang.png")       

        self.imgTentang = QLabel()   
        self.imgTentang.setPixmap(QPixmap(img_file))
        self.imgTentang.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        main_layout.addWidget(self.imgTentang)
        self.setLayout(main_layout)   
    
    def resource_path(self, relative_path):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, relative_path)    

class WindowTujuan(QWidget):
    def __init__(self):
        super().__init__()
        main_layout = QGridLayout()

        self.setWindowTitle("Tujuan")

        img_dir = self.resource_path("assets") 
        img_file = os.path.join(img_dir, "tujuan.png")       

        self.imgTentang = QLabel()   
        self.imgTentang.setPixmap(QPixmap(img_file))
        self.imgTentang.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        main_layout.addWidget(self.imgTentang)
        self.setLayout(main_layout)   
    
    def resource_path(self, relative_path):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, relative_path)  


class MyGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        ui_dir = self.resource_path("design")
        ui_file = os.path.join(ui_dir, "design.ui")        

        uic.loadUi(ui_file, self)
        self.show()

        self.windowTentang = WindowTentang()
        self.windowTujuan = WindowTujuan()
        
        self.pause = False        
        self.mode_pengenalan = False
        self.mode_pengenalan_foto = False
        self.mode_kamera_pengenalan = False
        self.mode_videofoto_pengenalan = False
        self.mode_videofoto_registrasi = False
        self.path_video = ""
        self.database_keys = []
        self.database_index = 0
        self.panjang_frame_video = 0
        self.frame_video = 0
        self.cameraIndex = None
        self.file_model_deteksi = ""
        self.file_model_pengenalan = ""
        self.lokasi_pickle = ""

        self.display_width = 100
        self.display_height = 100

        self.crop.setMaximumSize(self.crop.width(), self.crop.height())
        self.align.setMaximumSize(self.align.width(), self.align.height())
        
        self.pilihanTab.setCurrentIndex(0)

        self.lnDeteksi.setEnabled(False)
        self.btnModelDeteksi.setEnabled(False)
        self.lnPengenalan.setEnabled(False)
        self.btnModelPengenalan.setEnabled(False)

        self.pilihanTab.setEnabled(False)
        self.btnPauseRegistrasi.setEnabled(False)
        self.btnRegister.setEnabled(False)
        self.btnStopRegistrasi.setEnabled(False)  

        self.btnPausePengenalan.setEnabled(False)
        self.btnStopPengenalan.setEnabled(False)     

        # Tombol Panduan
        self.btnPanduan.clicked.connect(self.tombol_panduan) 

        # Tombol Mode Screen
        self.btnScreen.clicked.connect(self.tombol_screen)

        # Pilih tab registrasi/pengenalan/edit database
        self.btnRegistrasi.clicked.connect(self.tab_registrasi)
        self.btnPengenalan.clicked.connect(self.tab_pengenalan)
        self.btnEditDB.clicked.connect(self.tab_edit_database)

        # Tombol refresh kamera
        self.refreshCamRegistrasi.clicked.connect(self.refresh_cam_registrasi)
        self.refreshCamPengenalan.clicked.connect(self.refresh_cam_pengenalan)

        # Dialog file model deteksi wajah
        self.btnModelDeteksi.clicked.connect(self.dialog_deteksi_wajah)

        # Dialog file model pengenalan wajah
        self.btnModelPengenalan.clicked.connect(self.dialog_pengenalan_wajah)    

        # Ubah nilai threshold similarity
        self.btnSimilarity.clicked.connect(self.threshold_similarity)    

        # Pilih input (tab registrasi)
        self.btnKameraRegistrasi.clicked.connect(self.kamera_registrasi)
        self.btnVideoFotoRegistrasi.clicked.connect(self.foto_registrasi)
        self.btnLokasiVideoFotoR.clicked.connect(self.lokasi_video_foto_registrasi)    

        # Lokasi penyimpanan gambar wajah
        self.btnSimpanWajah.clicked.connect(self.dialog_simpan_database)

        # Edit nama wajah
        self.btnNamaWajah.clicked.connect(self.nama_wajah)
        self.btnEditNama.clicked.connect(self.edit_nama_wajah)
        self.btnBatalEdit.clicked.connect(self.batal_edit_nama)

        # Pilih input (tab pengenalan)
        self.btnKameraPengenalan.clicked.connect(self.kamera_pengenalan)
        self.btnVideoFotoPengenalan.clicked.connect(self.video_foto_pengenalan)
        self.btnLokasiVideoFoto.clicked.connect(self.lokasi_video_foto_pengenalan)

        # Lokasi database
        self.btnLokasiDB.clicked.connect(self.dialog_lokasi_database)

        # Tombol-tombol Tab Registrasi
        self.btnStartRegistrasi.clicked.connect(self.tombol_start)
        self.btnPauseRegistrasi.clicked.connect(self.tombol_pause)
        self.btnStopRegistrasi.clicked.connect(self.tombol_stop)
        self.btnRegister.clicked.connect(self.tombol_register)    

        # Tombol-tombol Tab Pengenalan
        self.btnStartPengenalan.clicked.connect(self.tombol_start_pengenalan)
        self.btnPausePengenalan.clicked.connect(self.tombol_pause_pengenalan)
        self.btnStopPengenalan.clicked.connect(self.tombol_stop_pengenalan)

        # Lokasi file database yang akan diedit
        self.btnEditFileDB.clicked.connect(self.dialog_edit_database)

        # Tombol-tombol Tab Edit Database
        self.btnNextFrame.clicked.connect(self.tombol_next_frame)
        self.btnPrevFrame.clicked.connect(self.tombol_prev_frame)
        self.btnHapusFrame.clicked.connect(self.tombol_hapus_frame)

        # Tombol tentang
        self.btnTentang.clicked.connect(self.tombol_tentang)

        # Tombol tujuan
        self.btnTujuan.clicked.connect(self.tombol_tujuan)

        # Tombol keluar
        self.btnExit.clicked.connect(self.tombol_exit)        

        self.thread = VideoThread(self)
        self.thread.detection_signal.connect(self.update_detection)
        self.thread.crop_signal.connect(self.update_crop)
        self.thread.alignment_signal.connect(self.update_align)
        self.thread.original_face_signal.connect(self.update_original)
        self.thread.similar_face_signal.connect(self.update_similar)
        self.thread.stylesheet_signal.connect(self.update_stylesheet)
        self.thread.face_name_signal.connect(self.update_face_name)
        self.thread.error_signal.connect(self.display_error_message)
    
    def display_error_message(self):
        QMessageBox.information(None, "Error", "Kamera tidak dapat dibaca. Coba lagi dengan menekan tombol start.") 
        
    def tombol_panduan(self):
        pdf_dir = self.resource_path("assets")
        pdf_file = os.path.join(pdf_dir, "Petunjuk Penggunaan.pdf")   
        os.startfile(pdf_file)
    
    def tombol_screen(self):
        if self.btnScreen.text() == "Mode Fullscreen":
            self.showFullScreen()
            self.btnScreen.setText("Mode Window")
        else:
            self.showNormal()
            self.btnScreen.setText("Mode Fullscreen")
    
    def resource_path(self, relative_path):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, relative_path)    

    def refresh_cam_registrasi(self):
        self.boxKameraRegistrasi.clear()
        cameraList = QMediaDevices.videoInputs()        
        for c in cameraList:
            self.boxKameraRegistrasi.addItem(c.description())

    def refresh_cam_pengenalan(self):
        self.boxKameraPengenalan.clear()
        cameraList = QMediaDevices.videoInputs()        
        for c in cameraList:
            self.boxKameraPengenalan.addItem(c.description())

    def dialog_deteksi_wajah(self):        
        file = QFileDialog.getOpenFileName(self, "Masukkan file model deteksi wajah", "", "ONNX File (*.onnx)")
        if file:
            self.file_model_deteksi = str(file[0])
            self.lnDeteksi.setText(self.file_model_deteksi)            
    
    def dialog_pengenalan_wajah(self):        
        file = QFileDialog.getOpenFileName(self, "Masukkan file model pengenalan wajah", "", "ONNX File (*.onnx)")
        if file:
            self.file_model_pengenalan = str(file[0])
            self.lnPengenalan.setText(self.file_model_pengenalan)           
    
    def threshold_similarity(self):
        if self.btnSimilarity.text() == "Terapkan":
            self.btnSimilarity.setText("Ganti")
            self.valSimilarity.setEnabled(False)
        else:
            self.btnSimilarity.setText("Terapkan")
            self.valSimilarity.setEnabled(True)

    def tab_registrasi(self):
        self.mode_pengenalan = False
        self.pilihanTab.setEnabled(True)
        self.pilihanTab.setCurrentIndex(0)

        self.lnDeteksi.setEnabled(True)
        self.btnModelDeteksi.setEnabled(True)
        self.lnPengenalan.setEnabled(True)
        self.btnModelPengenalan.setEnabled(True)

        self.btnSimilarity.setEnabled(False)
        self.valSimilarity.setEnabled(False)

        self.clear_all_labels()

        self.lnLokasiSimpanDB.clear()
        self.boxKameraRegistrasi.clear()
        self.lnVideoFotoRegistrasi.clear()
        self.lnNamaWajah.clear()
        self.lnNamaWajah.setEnabled(True)
        self.btnNamaWajah.setText("Terapkan")
        self.btnStartRegistrasi.setEnabled(True)
        self.listDatabase.clear()
        if self.btnKameraRegistrasi.isChecked() == False:
            self.boxKameraRegistrasi.setEnabled(False)
            self.refreshCamRegistrasi.setEnabled(False)

            self.btnKameraRegistrasi.setCheckable(False)
            self.btnKameraRegistrasi.setChecked(False)
            self.btnKameraRegistrasi.setCheckable(True) 

        if self.btnVideoFotoRegistrasi.isChecked() == False:
            self.lnVideoFotoRegistrasi.setEnabled(False)
            self.btnLokasiVideoFotoR.setEnabled(False)  

            self.btnVideoFotoRegistrasi.setCheckable(False)
            self.btnVideoFotoRegistrasi.setChecked(False)
            self.btnVideoFotoRegistrasi.setCheckable(True)        
        
    
    def tab_pengenalan(self):
        self.mode_pengenalan = True
        self.pilihanTab.setEnabled(True)
        self.pilihanTab.setCurrentIndex(1)

        self.lnDeteksi.setEnabled(True)
        self.btnModelDeteksi.setEnabled(True)
        self.lnPengenalan.setEnabled(True)
        self.btnModelPengenalan.setEnabled(True)

        self.btnSimilarity.setEnabled(True)
        self.valSimilarity.setEnabled(True)

        self.listDatabase.clear()
        self.lnLokasiDB.clear()
        self.boxKameraPengenalan.clear()
        self.lnVideoFotoPengenalan.clear()
        self.btnStartPengenalan.setEnabled(True)
        self.clear_all_labels()

        if self.btnKameraPengenalan.isChecked() == False:
            self.boxKameraPengenalan.setEnabled(False)
            self.refreshCamPengenalan.setEnabled(False)

            self.btnKameraPengenalan.setCheckable(False)
            self.btnKameraPengenalan.setChecked(False)
            self.btnKameraPengenalan.setCheckable(True) 

        if self.btnVideoFotoPengenalan.isChecked() == False:
            self.lnVideoFotoPengenalan.setEnabled(False)
            self.btnLokasiVideoFoto.setEnabled(False)  

            self.btnVideoFotoPengenalan.setCheckable(False)
            self.btnVideoFotoPengenalan.setChecked(False)
            self.btnVideoFotoPengenalan.setCheckable(True) 
    
    def tab_edit_database(self):
        self.mode_pengenalan = False
        self.pilihanTab.setEnabled(True)
        self.pilihanTab.setCurrentIndex(2)

        self.lnDeteksi.setEnabled(False)
        self.btnModelDeteksi.setEnabled(False)
        self.lnPengenalan.setEnabled(False)
        self.btnModelPengenalan.setEnabled(False)

        self.btnPrevFrame.setEnabled(False)
        self.btnNextFrame.setEnabled(False)
        self.btnHapusFrame.setEnabled(False)

        self.btnSimilarity.setEnabled(False)
        self.valSimilarity.setEnabled(False)

        self.clear_all_labels()
        self.lnEditFileDB.clear()
        self.lnEditNama.clear()
        self.lnEditNama.setEnabled(False)
        self.btnEditNama.setEnabled(True)
        self.btnEditNama.setText("Ganti")
        self.btnBatalEdit.setEnabled(False)
        self.listDatabase.clear()
        self.database_keys = []
    
    def kamera_registrasi(self):
        self.mode_videofoto_registrasi = False
        self.mode_videofoto_pengenalan = False  
        self.boxKameraRegistrasi.setEnabled(True)
        self.refreshCamRegistrasi.setEnabled(True)
        self.lnVideoFotoRegistrasi.setEnabled(False)
        self.btnLokasiVideoFotoR.setEnabled(False)
        self.boxKameraRegistrasi.clear()
        self.lnVideoFotoRegistrasi.clear()

        self.btnStartRegistrasi.setEnabled(True)

        # Tambah list kamera ke combobox
        cameraList = QMediaDevices.videoInputs()        
        for c in cameraList:
            self.boxKameraRegistrasi.addItem(c.description())
    
    def foto_registrasi(self):
        self.mode_videofoto_registrasi = True
        self.boxKameraRegistrasi.setEnabled(False)
        self.refreshCamRegistrasi.setEnabled(False)
        self.lnVideoFotoRegistrasi.setEnabled(True)
        self.btnLokasiVideoFotoR.setEnabled(True)
        self.boxKameraRegistrasi.clear()

        self.btnStartRegistrasi.setEnabled(False)
        self.btnPauseRegistrasi.setEnabled(False)
        self.btnStopRegistrasi.setEnabled(False)

    def lokasi_video_foto_registrasi(self):
        if self.lnDeteksi.text() == "" or self.lnPengenalan.text() == "":            
            QMessageBox.information(None, "Error", "Mohon masukkan file model deteksi & pengenalan pada bagian Setting.")
        elif self.lnLokasiSimpanDB.text() == "":
            QMessageBox.information(None, "Error", "Pilih lokasi untuk menyimpan file database terlebih dahulu!") 
        else:
            file_video_foto = QFileDialog.getOpenFileName(self, "Masukkan gambar/video subjek yang akan diregistrasi", "", "Image/Video Files (*.jpg *.jpeg *.png *.bmp *.mp4)")
            if file_video_foto:
                self.clear_all_labels()
                path_file = str(file_video_foto[0])
                self.lnVideoFotoRegistrasi.setText(path_file)
                file_format = path_file.split('.')[-1]
                if file_format.lower() in ['jpg', 'jpeg', 'png', 'bmp']:
                    self.btnStartRegistrasi.setEnabled(False)
                    self.btnRegister.setEnabled(True)  
                    self.process_image(path_file)
                else:                    
                    self.btnStartRegistrasi.setEnabled(True)
                    self.path_video = path_file

    def update_list_database(self, database):
        name_counts = {}
        for key in database.keys():                
            name = key.split("_")[0]
            if name == "img":
                pass
            else:
                if name not in name_counts:
                    name_counts[name] = 0
                name_counts[name] += 1

        self.listDatabase.clear()
        for name, count in name_counts.items():
            str_list = name + " (" + str(count) + " Frame)"                
            self.listDatabase.addItem(str_list)
    
    def dialog_simpan_database(self):
        file_database = QFileDialog.getSaveFileName(self, "Pilih lokasi penyimpanan database dan nama filenya", "", "Pickle File (*.pkl)")
        if file_database[0] != "":
            self.lnLokasiSimpanDB.setText(file_database[0])
            if os.path.isfile(file_database[0]):
                self.lokasi_pickle = file_database[0]
                pickle_database = open(self.lokasi_pickle, "rb")
                database = pickle.load(pickle_database)
                pickle_database.close()
                self.update_list_database(database)
                
            else:
                 self.listDatabase.clear()
    
    def nama_wajah(self):
        if self.btnNamaWajah.text() == "Terapkan":
            if self.lnNamaWajah.text() == "":
                QMessageBox.information(None, "Error", "Nama wajah tidak boleh kosong!")
            else:
                if self.lnLokasiSimpanDB.text() == "":
                    QMessageBox.information(None, "Error", "Pilih folder penyimpanan wajah terlebih dahulu!")
                else:
                    self.btnNamaWajah.setText("Ganti")
                    self.lnNamaWajah.setEnabled(False)
        else:
            self.btnNamaWajah.setText("Terapkan")
            self.lnNamaWajah.setEnabled(True)
    
    def ukuran_file(self, lokasi):
        return os.path.getsize(lokasi)
    
    def tombol_start(self):        
        self.thread.isStopped = False
        self.thread.isActive = True  
        self.refresh_cam_registrasi()
        
        if self.lnDeteksi.text() == "" or self.lnPengenalan.text() == "":
            QMessageBox.information(None, "Error", "Mohon masukkan file model deteksi & pengenalan pada bagian Setting.")
        elif self.lnLokasiSimpanDB.text() == "":
            QMessageBox.information(None, "Error", "Pilih lokasi untuk menyimpan file database terlebih dahulu!") 
        elif self.boxKameraRegistrasi.currentText() == "":
            QMessageBox.information(None, "Error", "Webcam tidak terdeteksi.")
        else:
            ukuran_yunet = self.ukuran_file(self.lnDeteksi.text())
            ukuran_sface = self.ukuran_file(self.lnPengenalan.text())
            if ukuran_sface > ukuran_yunet:
                self.cameraIndex = self.boxKameraRegistrasi.currentIndex()
                self.btnStartRegistrasi.setEnabled(False)      
                self.btnPauseRegistrasi.setEnabled(True)    
                self.btnRegister.setEnabled(True)      
                self.btnStopRegistrasi.setEnabled(True)

                self.btnRegistrasi.setEnabled(False)
                self.btnPengenalan.setEnabled(False)
                self.btnEditDB.setEnabled(False)
                self.lnDeteksi.setEnabled(False)
                self.lnPengenalan.setEnabled(False)
                self.btnModelDeteksi.setEnabled(False)
                self.btnModelPengenalan.setEnabled(False)

                self.btnKameraRegistrasi.setEnabled(False)
                self.btnVideoFotoRegistrasi.setEnabled(False)            
                self.lnLokasiSimpanDB.setEnabled(False)
                self.btnSimpanWajah.setEnabled(False)
                self.boxKameraRegistrasi.setEnabled(False)
                self.refreshCamRegistrasi.setEnabled(False)
                self.lnVideoFotoRegistrasi.setEnabled(False)
                self.btnLokasiVideoFotoR.setEnabled(False)                

                self.thread.start()
            else:
                QMessageBox.information(None, "Error", "File model yang dimasukkan tidak sesuai. Mohon dicek kembali.")
            
    def tombol_pause(self):
        self.pause = True        
        self.btnStartRegistrasi.setEnabled(True)
        self.btnPauseRegistrasi.setEnabled(False)
        self.btnStopRegistrasi.setEnabled(True)
        self.thread.stop()

    def tombol_stop(self):
        self.pause = False              

        self.thread.isStopped = True
        self.clear_all_labels()

        self.btnStartRegistrasi.setEnabled(True)      
        self.btnPauseRegistrasi.setEnabled(False)    
        self.btnRegister.setEnabled(False)      
        self.btnStopRegistrasi.setEnabled(False)

        self.btnRegistrasi.setEnabled(True)
        self.btnPengenalan.setEnabled(True)
        self.btnEditDB.setEnabled(True)
        self.lnDeteksi.setEnabled(True)
        self.lnPengenalan.setEnabled(True)
        self.btnModelDeteksi.setEnabled(True)
        self.btnModelPengenalan.setEnabled(True)

        self.btnKameraRegistrasi.setEnabled(True)
        self.btnVideoFotoRegistrasi.setEnabled(True)        
        self.lnLokasiSimpanDB.setEnabled(True)
        self.btnSimpanWajah.setEnabled(True)

        if self.btnKameraRegistrasi.isChecked():
            self.boxKameraRegistrasi.setEnabled(True)
            self.refreshCamRegistrasi.setEnabled(True)
        if self.btnVideoFotoRegistrasi.isChecked():
            self.lnVideoFotoRegistrasi.setEnabled(True)
            self.btnLokasiVideoFotoR.setEnabled(True)

        self.lnNamaWajah.setEnabled(True)
        self.btnNamaWajah.setEnabled(True)
    
    def tombol_register(self):
        global aligned_img
        
        if self.lnLokasiSimpanDB.text() == "":
            QMessageBox.information(None, "Error", "Mohon masukkan folder penyimpanan database.")
        elif self.lnNamaWajah.text() == "":
            QMessageBox.information(None, "Error", "Mohon isi nama wajah yang akan diregistrasi.")
        elif self.btnNamaWajah.text() == "Terapkan":
            QMessageBox.information(None, "Error", "Klik tombol 'Terapkan' pada nama wajah terlebih dahulu.")
        else:             
            # Simpan gambar wajah ke folder database 
            duplikat = False
            now = datetime.datetime.now()
            time_now = now.strftime("%H%M%S")

            self.lokasi_pickle = self.lnLokasiSimpanDB.text()
            
            # Simpan database dalam format pickle
            database = {}

            if os.path.isfile(self.lokasi_pickle):
                pickle_database = open(self.lokasi_pickle, "rb")
                database = pickle.load(pickle_database)
                pickle_database.close()            

            nama_file_gambar = "img_" + self.lnNamaWajah.text() + "_" + time_now
            database[nama_file_gambar] = aligned_img
            
            nama_wajah = self.lnNamaWajah.text() + "_" + time_now
            model_pengenalan = cv2.FaceRecognizerSF.create(self.file_model_pengenalan, "")

            if aligned_img is not None: 
                fitur_wajah = model_pengenalan.feature(aligned_img)

                for value in database.values():
                    if np.array_equal(value, fitur_wajah):
                        duplikat = True
                        break
                
                if duplikat:
                    QMessageBox.information(None, "Error", "Tidak dapat mendaftar wajah yang sudah dimasukkan sebelumnya.")
                    duplikat = False
                else:
                    database[nama_wajah] = fitur_wajah
                    self.lokasi_pickle = self.lnLokasiSimpanDB.text()
                    pickle_database = open(self.lokasi_pickle, "wb")
                    pickle.dump(database, pickle_database)
                    pickle_database.close()  
                    QMessageBox.information(None, "Info", 'Wajah "' + self.lnNamaWajah.text() + '" berhasil ditambahkan.')
            else:
                QMessageBox.information(None, "Error", "Gagal.")
            pickle_database = open(self.lokasi_pickle, "rb")
            database = pickle.load(pickle_database)
            pickle_database.close()

            self.update_list_database(database)   

    def kamera_pengenalan(self):          
        self.mode_kamera_pengenalan = True
        self.mode_videofoto_registrasi = False
        self.mode_videofoto_pengenalan = False        
        self.boxKameraPengenalan.setEnabled(True)
        self.refreshCamPengenalan.setEnabled(True)
        self.lnVideoFotoPengenalan.setEnabled(False)
        self.btnLokasiVideoFoto.setEnabled(False)        
        self.boxKameraPengenalan.clear()
        self.lnVideoFotoPengenalan.clear()

        self.btnStartPengenalan.setEnabled(True)        

        # Tambah list kamera ke combobox
        cameraList = QMediaDevices.videoInputs()        
        for c in cameraList:
            self.boxKameraPengenalan.addItem(c.description())
    
    def video_foto_pengenalan(self):   
        self.mode_kamera_pengenalan = False
        self.mode_videofoto_pengenalan = True
        self.boxKameraPengenalan.setEnabled(False)
        self.refreshCamPengenalan.setEnabled(False)
        self.lnVideoFotoPengenalan.setEnabled(True)
        self.btnLokasiVideoFoto.setEnabled(True)
        self.boxKameraPengenalan.clear()

        #self.btnStartPengenalan.setEnabled(True)
        self.btnPausePengenalan.setEnabled(False)
        self.btnStopPengenalan.setEnabled(False)

    def lokasi_video_foto_pengenalan(self): 
        if self.lnDeteksi.text() == "" or self.lnPengenalan.text() == "":            
            QMessageBox.information(None, "Error", "Mohon masukkan file model deteksi & pengenalan pada bagian Setting.")
        elif self.lnLokasiDB.text() == "":
            QMessageBox.information(None, "Error", "Pilih file database terlebih dahulu!") 
        else:       
            img_videofoto_file = QFileDialog.getOpenFileName(self, "Masukkan video/foto yang akan dikenali", "", "Image/Video Files (*.jpg *.jpeg *.png *.bmp *.mp4)")
            if img_videofoto_file:
                self.clear_all_labels()
                path_file = str(img_videofoto_file[0])            
                self.lnVideoFotoPengenalan.setText(path_file)
                file_format = path_file.split('.')[-1]
                if file_format.lower() in ['jpg', 'jpeg', 'png', 'bmp']:
                    if self.btnSimilarity.text() == "Terapkan":
                        self.lnVideoFotoPengenalan.clear()
                        QMessageBox.information(None, "Error", "Klik tombol 'Terapkan' pada nilai threshold cosine similarity terlebih dahulu.")
                    else:
                        self.btnStartPengenalan.setEnabled(False)    
                        self.process_image(path_file)
                else:                    
                    self.btnStartPengenalan.setEnabled(True)
                    self.path_video = path_file
                    #self.process_video(path_file)

    def dialog_lokasi_database(self):        
        file_database = QFileDialog.getOpenFileName(self, "Masukkan file database", "", "Pickle File (*.pkl)")
        
        if file_database[0] != "":
            self.lnLokasiDB.setText(file_database[0])
            self.lokasi_pickle = file_database[0]

            pickle_database = open(self.lokasi_pickle, "rb")
            database = pickle.load(pickle_database)
            pickle_database.close()       
            self.update_list_database(database)     

            if database == {}:
                self.lnLokasiDB.clear()
                self.listDatabase.clear()
                QMessageBox.information(None, "Error", "File pickle tidak dapat dibaca. Buat ulang database melalui menu registrasi wajah.")       

    def tombol_start_pengenalan(self):
        self.thread.isStopped = False
        self.thread.isActive = True
        self.refresh_cam_pengenalan() 
        
        if self.lnDeteksi.text() == "" or self.lnPengenalan.text() == "":            
            QMessageBox.information(None, "Error", "Mohon masukkan file model deteksi & pengenalan pada bagian Setting.")        
        elif self.lnLokasiDB.text() == "":            
            QMessageBox.information(None, "Error", "Pilih lokasi folder database terlebih dahulu.")        
        elif self.boxKameraPengenalan.currentText() == "":
            QMessageBox.information(None, "Error", "Webcam tidak terdeteksi.")
        else:            
            if self.lnVideoFotoPengenalan.text() == "":
                if self.mode_videofoto_pengenalan:
                    QMessageBox.information(None, "Error", "Pilih file video/foto yang akan dikenali terlebih dahulu.")
            
            if self.btnSimilarity.text() == "Terapkan":
                QMessageBox.information(None, "Error", "Klik tombol 'Terapkan' pada nilai threshold cosine similarity terlebih dahulu.")
            else:
                ukuran_yunet = self.ukuran_file(self.lnDeteksi.text())
                ukuran_sface = self.ukuran_file(self.lnPengenalan.text())
                if ukuran_sface > ukuran_yunet:
                    self.cameraIndex = self.boxKameraPengenalan.currentIndex()
                    self.btnStartPengenalan.setEnabled(False)
                    self.btnPausePengenalan.setEnabled(True)            
                    self.btnStopPengenalan.setEnabled(True)                

                    self.btnRegistrasi.setEnabled(False)
                    self.btnPengenalan.setEnabled(False)
                    self.btnEditDB.setEnabled(False)
                    self.lnDeteksi.setEnabled(False)
                    self.lnPengenalan.setEnabled(False)
                    self.btnModelDeteksi.setEnabled(False)
                    self.btnModelPengenalan.setEnabled(False)

                    self.btnKameraPengenalan.setEnabled(False)
                    self.btnVideoFotoPengenalan.setEnabled(False)
                    self.lnLokasiDB.setEnabled(False)
                    self.btnLokasiDB.setEnabled(False)
                    self.boxKameraPengenalan.setEnabled(False)
                    self.refreshCamPengenalan.setEnabled(False)
                    self.lnVideoFotoPengenalan.setEnabled(False)
                    self.btnLokasiVideoFoto.setEnabled(False)
                    self.thread.start()
                else:
                    QMessageBox.information(None, "Error", "File model yang dimasukkan tidak sesuai. Mohon dicek kembali.")

    def tombol_pause_pengenalan(self):
        self.pause = True       
        self.btnStartPengenalan.setEnabled(True)
        self.btnPausePengenalan.setEnabled(False)
        self.btnStopPengenalan.setEnabled(True)
        self.thread.stop()

    def tombol_stop_pengenalan(self):        
        self.pause = False       
        self.btnStartPengenalan.setEnabled(True)
        self.btnPausePengenalan.setEnabled(False)
        self.btnStopPengenalan.setEnabled(False)

        self.btnRegistrasi.setEnabled(True)
        self.btnPengenalan.setEnabled(True)
        self.btnEditDB.setEnabled(True)
        self.lnDeteksi.setEnabled(True)
        self.lnPengenalan.setEnabled(True)
        self.btnModelDeteksi.setEnabled(True)
        self.btnModelPengenalan.setEnabled(True)

        self.btnKameraPengenalan.setEnabled(True)
        self.btnVideoFotoPengenalan.setEnabled(True)
        self.lnLokasiDB.setEnabled(True)
        self.btnLokasiDB.setEnabled(True)       

        if self.btnKameraPengenalan.isChecked():
            self.boxKameraPengenalan.setEnabled(True)
            self.refreshCamPengenalan.setEnabled(True)
        if self.btnVideoFotoPengenalan.isChecked():
            self.lnVideoFotoPengenalan.setEnabled(True)
            self.btnLokasiVideoFoto.setEnabled(True)

        self.thread.isStopped = True
        
        self.clear_all_labels() 

    def tombol_tentang(self):
        self.windowTentang.close()
        self.windowTentang.show()

    def tombol_tujuan(self):
        self.windowTujuan.close()
        self.windowTujuan.show()

    def tombol_exit(self):
        sys.exit()

    def dialog_edit_database(self):
        self.database_keys = []
        file_database = QFileDialog.getOpenFileName(self, "Masukkan file database", "", "Pickle File (*.pkl)")
        
        if file_database[0] != "":
            self.lnEditFileDB.setText(str(file_database[0]))            
            
            self.lokasi_pickle = self.lnEditFileDB.text()
            pickle_database = open(self.lokasi_pickle, "rb")
            database = pickle.load(pickle_database)
            pickle_database.close()
                        
            if self.database_keys == [] and database != {}:
                self.btnNextFrame.setEnabled(True)
                self.btnPrevFrame.setEnabled(True)
                self.btnHapusFrame.setEnabled(True)
                for key in database.keys():                    
                    if "img" in key:
                        self.database_keys.append(key)

                self.update_similar(database[self.database_keys[0]])
                self.display_nama_wajah(self.database_keys[self.database_index])  
                self.update_list_database(database)
            else:
                self.lnEditFileDB.clear()
                self.listDatabase.clear()
                QMessageBox.information(None, "Error", "File pickle tidak dapat dibaca. Buat ulang database melalui menu registrasi wajah.")   
        
    def edit_nama_wajah(self):
        if self.btnEditNama.text() == "Terapkan":            
            if self.lnEditFileDB.text() == "":
                QMessageBox.information(None, "Error", "Pilih file database terlebih dahulu!") 
                self.lnEditNama.clear()
            else:
                if self.lnEditNama.text() == "":
                    QMessageBox.information(None, "Error", "Nama wajah tidak boleh kosong!")
                else:
                    if self.database_keys[self.database_index].split("_")[1] == self.lnEditNama.text():
                        QMessageBox.information(None, "Error", "Nama yang dimasukkan sama dengan sebelumnya.")
                    elif "_" in self.lnEditNama.text():
                        QMessageBox.information(None, "Error", 'Tidak dapat menggunakan simbol "_"')
                    else:
                        self.btnPrevFrame.setEnabled(True)
                        self.btnNextFrame.setEnabled(True)
                        self.btnHapusFrame.setEnabled(True)
                        self.btnEditNama.setText("Ganti")
                        self.lnEditNama.setEnabled(False)
                        self.btnBatalEdit.setEnabled(False)
                        self.lokasi_pickle = self.lnEditFileDB.text()
                        pickle_database = open(self.lokasi_pickle, "rb")
                        database = pickle.load(pickle_database)
                        pickle_database.close()
                        new_img_name = "img_" + self.lnEditNama.text() + "_" + self.database_keys[self.database_index].split("_")[2]
                        new_name = self.lnEditNama.text() + "_" + self.database_keys[self.database_index].split("_")[2]

                        new_database_1 = dict((key.replace(self.database_keys[self.database_index], new_img_name), value) for key, value in database.items())
                        new_database_2 = dict((key.replace(self.database_keys[self.database_index].replace("img_", ""), new_name), value) for key, value in new_database_1.items())
                        
                        QMessageBox.information(None, "Info", 'Nama wajah "' + self.database_keys[self.database_index].split("_")[1] + '" berhasil diubah menjadi "' + self.lnEditNama.text() + '".')  

                        self.database_keys = [key.replace(self.database_keys[self.database_index], new_img_name) for key in self.database_keys]
                        
                        pickle_database = open(self.lokasi_pickle, "wb")
                        pickle.dump(new_database_2, pickle_database)
                        pickle_database.close()
                        self.update_list_database(new_database_2)
                        

        else:
            self.btnPrevFrame.setEnabled(False)
            self.btnNextFrame.setEnabled(False)
            self.btnHapusFrame.setEnabled(False)
            self.btnEditNama.setText("Terapkan")
            self.lnEditNama.setEnabled(True)
            self.btnBatalEdit.setEnabled(True)

    def batal_edit_nama(self):
        if len(self.database_keys) > 0:
            self.display_nama_wajah(self.database_keys[self.database_index])
            self.btnPrevFrame.setEnabled(True)
            self.btnNextFrame.setEnabled(True)
            self.btnHapusFrame.setEnabled(True)
        self.btnEditNama.setText("Ganti")
        self.lnEditNama.setEnabled(False)
        self.btnBatalEdit.setEnabled(False)

    def tombol_next_frame(self):
        self.lokasi_pickle = self.lnEditFileDB.text()
        pickle_database = open(self.lokasi_pickle, "rb")
        database = pickle.load(pickle_database)
        pickle_database.close()
        self.database_index += 1
        if self.database_index < len(self.database_keys):
            self.update_similar(database[self.database_keys[self.database_index]])         
            self.display_nama_wajah(self.database_keys[self.database_index])  
        else:
            self.database_index = 0
            self.update_similar(database[self.database_keys[self.database_index]])           
            self.display_nama_wajah(self.database_keys[self.database_index])        

    def tombol_prev_frame(self):
        self.lokasi_pickle = self.lnEditFileDB.text()
        pickle_database = open(self.lokasi_pickle, "rb")
        database = pickle.load(pickle_database)
        pickle_database.close()        
        self.database_index -= 1
        if self.database_index >= 0:
            self.update_similar(database[self.database_keys[self.database_index]])            
            self.display_nama_wajah(self.database_keys[self.database_index])  
        else:
            self.database_index = len(self.database_keys) - 1
            self.update_similar(database[self.database_keys[self.database_index]])           
            self.display_nama_wajah(self.database_keys[self.database_index]) 

    def tombol_hapus_frame(self):
        self.lokasi_pickle = self.lnEditFileDB.text()
        pickle_database = open(self.lokasi_pickle, "rb")
        database = pickle.load(pickle_database)
        pickle_database.close()  

        if self.database_keys != []:  
            del database[self.database_keys[self.database_index]]
            del database[self.database_keys[self.database_index].replace("img_", "")]

            QMessageBox.information(None, "Info", 'Wajah "' + self.database_keys[self.database_index].split("_")[1] + '" berhasil dihapus.')
            self.database_keys.remove(self.database_keys[self.database_index])

            if self.database_keys != []:                 
                if self.database_index == 0:
                    self.update_similar(database[self.database_keys[self.database_index]])
                    self.display_nama_wajah(self.database_keys[self.database_index])  
                else:
                    self.database_index -= 1
                    self.update_similar(database[self.database_keys[self.database_index]])
                    self.display_nama_wajah(self.database_keys[self.database_index])                    
            else:
                self.similarFace.clear()
                self.similarFace.setText("Similar Face")
                self.lnEditFileDB.clear()
                self.lnEditNama.clear()
                self.btnPrevFrame.setEnabled(False)
                self.btnNextFrame.setEnabled(False)
                self.btnHapusFrame.setEnabled(False)
                QMessageBox.information(None, "Error", "Semua data wajah sudah dihapus. Silakan tambahkan data baru melalui menu registrasi wajah.")
        else:
            self.similarFace.clear()
            self.similarFace.setText("Similar Face")
            QMessageBox.information(None, "Error", "Data wajah kosong. Silakan tambahkan data baru melalui menu registrasi wajah.")

        pickle_database = open(self.lokasi_pickle, "wb")
        pickle.dump(database, pickle_database)
        pickle_database.close()
        self.update_list_database(database)
    
    def display_nama_wajah(self, nama):
        nama = nama.split("_")[1]
        self.lnEditNama.setText(nama)
    
    def process_image(self, path_gambar):
        global aligned_img
        self.file_model_deteksi = self.lnDeteksi.text()
        self.file_model_pengenalan = self.lnPengenalan.text()
        
        original_img = cv2.imread(path_gambar)
        h, w, _ = original_img.shape
        model_yunet = cv2.FaceDetectorYN.create(
                    model=self.file_model_deteksi,
                    config="",
                    input_size=(w, h),
                    score_threshold=0.7,
                    nms_threshold=0.3,
                    top_k=1)
        
        model_sface = cv2.FaceRecognizerSF.create(model=self.file_model_pengenalan, config="")

        faces = model_yunet.detect(original_img)[1]
        if faces is not None:
            for face in faces:
                detected_img = self.visualize(original_img, face)
                face_img = self.crop_face(original_img, face)
                aligned_img = self.align_face(original_img, face, model_sface)        
             
        if detected_img is not None and face_img is not None:
            face_feature = model_sface.feature(aligned_img)
            if self.mode_pengenalan: 
                self.lokasi_pickle = self.lnLokasiDB.text()
                pickle_database = open(self.lokasi_pickle, "rb")
                database = pickle.load(pickle_database)
                pickle_database.close() 
                max_cosine = 0
                cosine_similarity_threshold = float(self.valSimilarity.text())
                identity = 'unknown'
                for key in database.keys():
                    name = key.split("_")[0]
                    if name != "img":
                        cosine_score = model_sface.match(face_feature, database[key])
                        if cosine_score > max_cosine:
                            max_cosine = cosine_score
                            identity = key
                
                str_max_cosine = "{:.3f}".format(round(max_cosine, 3))
                self.lcdSimilarity.display(str_max_cosine)
                if max_cosine >= cosine_similarity_threshold:
                    identity_image = database["img_" + identity]
                    self.update_similar(identity_image)
                    identity = identity.split("_")[0]                        
                else:
                    identity = 'unknown'
                    self.clear_all_labels()
                
                self.update_face_name(identity)

                self.update_original(aligned_img)

            self.update_detection(detected_img)        
            self.update_crop(face_img)
            self.update_align(aligned_img)
        else:
            self.update_detection(original_img)
        
    def clear_all_labels(self):
        if self.pause:
            pass
        else:
            self.detection.clear()
            self.detection.setText("Detection")
            self.crop.clear()
            self.crop.setText("Crop")
            self.align.clear()
            self.align.setText("Align")
            self.originalFace.clear()
            self.originalFace.setText("Original Face")
            self.similarFace.clear()
            self.similarFace.setText("Similar Face")      
            self.hasilPengenalan.clear()
    
    def clear_small_labels(self):
        if self.pause:
            pass
        else:
            self.crop.clear()
            self.crop.setText("Crop")
            self.align.clear()
            self.align.setText("Align")
            self.originalFace.clear()
            self.originalFace.setText("Original Face")
            self.similarFace.clear()
            self.similarFace.setText("Similar Face")      
            self.hasilPengenalan.clear()

    def clear_sf_label(self):
        self.similarFace.clear()
        self.similarFace.setText("Similar Face")    
    
    def crop_face(self, original_img, face):
        face_img = original_img.copy()
        x, y, w, h = np.maximum(face[0:4].astype(np.int32), 0)
        face_img = face_img[y:y + h, x:x + w]               
        return face_img
    
    def align_face(self, original_img, face, model_sface):
        aligned_img = model_sface.alignCrop(original_img, face)
        return aligned_img

    def visualize(self, original_img, face):
        detected_img = original_img.copy()
        x, y, w, h = np.maximum(face[0:4].astype(np.int32), 0)
        start_point = (x, y)
        end_point = (x + w, y + h)
        rectangle_color = (0, 255, 0)
        cv2.rectangle(detected_img, start_point, end_point, rectangle_color, thickness=2)
        return detected_img

    def closeEvent(self, event):
        print("exited")
        self.thread.stop()
        event.accept()

    def convert_cv_qt(self, cv_img):
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_format = QtGui.QImage(rgb_image.data, w, h, bytes_per_line, QtGui.QImage.Format.Format_RGB888)
        return QPixmap.fromImage(qt_format)

    @pyqtSlot(np.ndarray)
    def update_detection(self, cv_img): 
        h, w, _ = cv_img.shape
        # Resize
        if h > self.detection.height() or w > self.detection.width():
           h_ratio = self.detection.height() / h
           w_ratio = self.detection.width() / w
           scale_factor = min(h_ratio, w_ratio)
           h = int(h * scale_factor)
           w = int(w * scale_factor)
           dim = (w, h)
           cv_img = cv2.resize(cv_img, dim)

        qt_img = self.convert_cv_qt(cv_img)   
        self.detection.setPixmap(qt_img)    
        self.detection.repaint()

    @pyqtSlot(np.ndarray)
    def update_crop(self, face_img):
        face_img = face_img.copy()
        h, w, _ = face_img.shape

        # Resize
        if h > self.crop.height() or w > self.crop.width():
           h_ratio = self.crop.height() / h
           w_ratio = self.crop.width() / w
           scale_factor = min(h_ratio, w_ratio)
           h = int(h * scale_factor)
           w = int(w * scale_factor)
           dim = (w, h)
           face_img = cv2.resize(face_img, dim)

        bytes_per_line = 3 * w
        qt_format = QtGui.QImage(face_img, w, h, bytes_per_line, QtGui.QImage.Format.Format_BGR888)        
        qt_img = QPixmap.fromImage(qt_format)
        self.crop.setPixmap(qt_img)

    @pyqtSlot(np.ndarray)
    def update_align(self, face_img):
        h, w, _ = face_img.shape

        # Resize
        if h > self.align.height() or w > self.align.width():
           h_ratio = self.align.height() / h
           w_ratio = self.align.width() / w
           scale_factor = min(h_ratio, w_ratio)
           h = int(h * scale_factor)
           w = int(w * scale_factor)
           dim = (w, h)
           face_img = cv2.resize(face_img, dim)

        bytes_per_line = 3 * w
        qt_format = QtGui.QImage(face_img, w, h, bytes_per_line, QtGui.QImage.Format.Format_BGR888)
        qt_img = QPixmap.fromImage(qt_format)
        self.align.setPixmap(qt_img)        

    @pyqtSlot(np.ndarray)
    def update_original(self, face_img):
        h, w, _ = face_img.shape

        # Resize
        if h > self.originalFace.height() or w > self.originalFace.width():
           h_ratio = self.originalFace.height() / h
           w_ratio = self.originalFace.width() / w
           scale_factor = min(h_ratio, w_ratio)
           h = int(h * scale_factor)
           w = int(w * scale_factor)
           dim = (w, h)
           face_img = cv2.resize(face_img, dim)

        bytes_per_line = 3 * w
        qt_format = QtGui.QImage(face_img, w, h, bytes_per_line, QtGui.QImage.Format.Format_BGR888)
        qt_img = QPixmap.fromImage(qt_format)        
        self.originalFace.setPixmap(qt_img)
    
    @pyqtSlot(np.ndarray)
    def update_similar(self, face_img):
        h, w, _ = face_img.shape

        # Resize
        if h > self.similarFace.height() or w > self.similarFace.width():
           h_ratio = self.similarFace.height() / h
           w_ratio = self.similarFace.width() / w
           scale_factor = min(h_ratio, w_ratio)
           h = int(h * scale_factor)
           w = int(w * scale_factor)
           dim = (w, h)
           face_img = cv2.resize(face_img, dim)

        bytes_per_line = 3 * w
        qt_format = QtGui.QImage(face_img, w, h, bytes_per_line, QtGui.QImage.Format.Format_BGR888)
        qt_img = QPixmap.fromImage(qt_format)        
        self.similarFace.setPixmap(qt_img)
    
    @pyqtSlot(str)
    def update_stylesheet(self, stylesheet):
        self.hasilPengenalan.setStyleSheet(stylesheet)
    
    @pyqtSlot(str)
    def update_face_name(self, face_name):
        self.hasilPengenalan.setText(face_name)

def main():
    app = QApplication([])
    window = MyGUI()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
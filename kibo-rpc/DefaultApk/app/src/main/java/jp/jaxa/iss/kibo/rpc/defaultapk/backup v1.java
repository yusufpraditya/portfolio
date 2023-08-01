package jp.jaxa.iss.kibo.rpc.defaultapk;

import android.graphics.Bitmap;
import android.util.Log;

import java.lang.Math;
import jp.jaxa.iss.kibo.rpc.api.KiboRpcService;
import gov.nasa.arc.astrobee.Result;
import gov.nasa.arc.astrobee.types.Point;
import gov.nasa.arc.astrobee.types.Quaternion;

import com.google.zxing.BinaryBitmap;
import com.google.zxing.ChecksumException;
import com.google.zxing.FormatException;
import com.google.zxing.LuminanceSource;
import com.google.zxing.MultiFormatReader;
import com.google.zxing.Reader;
import com.google.zxing.NotFoundException;
import com.google.zxing.RGBLuminanceSource;
import com.google.zxing.common.HybridBinarizer;


/**
 * Class meant to handle commands from the Ground Data System and execute them in Astrobee
 */

public class YourService extends KiboRpcService {
    // roll (x), pitch (y), yaw (z)

    private double qua_w, qua_x, qua_y, qua_z;
    public static final String TAG = "TAG";

    // OTW P1-1
    private final Point POINT_P11 = new Point(11.5, -5.7, 4.5);
    private final double[] QUAT_P11 = new double[]{0, 0, 0};

    // OTW P1-3
    private final Point POINT_P13_1 = new Point(11, -5.5, 4.5);
    private final Point POINT_P13 = new Point(11, -5.5, 4.33);
    private final double[] QUAT_P13_1 = new double[]{0, 0, -90};
    private final double[] QUAT_P13 = new double[]{0, 90, -90};

    // OTW P1-2
    private final Point POINT_P12 = new Point(11, -6, 5.5);
    private final double[] QUAT_P12 = new double[]{0, -90, -90};

    // LEWATI RINTANGAN
    private final Point POINT_AVOID_1 = new Point(10.529,-6.2,5.5);
    private final Point POINT_AVOID_2 = new Point(10.529, -6.837, 5.5);
    private final Point POINT_AVOID_3 = new Point(11.161, -6.837, 5.5);
    private final double[] QUAT_AVOID_1 = new double[]{0, 0, -90};
    private final double[] QUAT_AVOID_2 = new double[]{0, 0, 0};
    private final double[] QUAT_AVOID_3 = new double[]{0, 0, -90};

    // OTW P2-3
    private final Point POINT_P23 = new Point(11, -7.7, 5.55);
    private final double[] QUAT_P23 = new double[]{0, -90, -90};

    // OTW P2-1
    private final Point POINT_P21 = new Point(10.3, -7.5, 4.7);
    private final double[] QUAT_P21 = new double[]{0, 0, -180};

    // OTW P2-2
    private final Point POINT_P22 = new Point(11.5, -8, 5);
    private final double[] QUAT_P22 = new double[]{0, 0, 0};

    private java.util.ArrayList<String> QR_LIST = null;
    int QR_COUNT = 0;

    @Override
    protected void runPlan1(){
        // write here your plan 1
        api.judgeSendStart();
        java.util.ArrayList<Point> trajectory;
        java.util.ArrayList<double[]> orient;
        Point[] arrayPoint = {POINT_P11, POINT_P13_1, POINT_P13, POINT_P12, POINT_AVOID_1, POINT_AVOID_2, POINT_AVOID_3, POINT_P23, POINT_P21, POINT_P22};
        double[][] arrayQuaternion = {QUAT_P11, QUAT_P13_1, QUAT_P13, QUAT_P12, QUAT_AVOID_1, QUAT_AVOID_2, QUAT_AVOID_3, QUAT_P23, QUAT_P21, QUAT_P22};
        trajectory = new java.util.ArrayList<>(java.util.Arrays.asList(arrayPoint));
        orient = new java.util.ArrayList<>(java.util.Arrays.asList(arrayQuaternion));

        moveRobot(trajectory, orient);
        double pos_x, pos_y, pos_z;
        for(int i = 0; i < QR_LIST.size(); i++){
            String text = QR_LIST.get(i);
            String[] arrSplit = text.split(", ");
            switch (arrSplit[0]){
                case "pos_x":
                    pos_x = Double.parseDouble(arrSplit[1]);
                    Log.d(TAG, "Found: " + pos_x);
                    break;
                case "pos_y":
                    pos_y = Double.parseDouble(arrSplit[1]);
                    Log.d(TAG, "Found: " + pos_y);
                    break;
                case "pos_z":
                    pos_z = Double.parseDouble(arrSplit[1]);
                    Log.d(TAG, "Found: " + pos_z);
                    break;
                case "qua_x":
                    qua_x = Double.parseDouble(arrSplit[1]);
                    Log.d(TAG, "Found: " + qua_x);
                    break;
                case "qua_y":
                    qua_y = Double.parseDouble(arrSplit[1]);
                    Log.d(TAG, "Found: " + qua_y);
                    break;
                case "qua_z":
                    qua_z = Double.parseDouble(arrSplit[1]);
                    Log.d(TAG, "Found: " + qua_z);
                    break;
            }
        }
    }

    @Override
    protected void runPlan2(){
        // write here your plan 2
        // api.judgeSendStart();

        // Point[] arrayPoint = {POINT_P11, POINT_P13, POINT_P12, POINT_AVOID_1, POINT_AVOID_2, POINT_AVOID_3, POINT_P23, POINT_P21, POINT_P22};
        // double[][] arrayQuaternion = {QUAT_P11, QUAT_P13, QUAT_P12, QUAT_AVOID_1, QUAT_AVOID_2, QUAT_AVOID_3, QUAT_P23, QUAT_P21, QUAT_P22};
        // trajectory = new java.util.ArrayList<>(java.util.Arrays.asList(arrayPoint));
        // orient = new java.util.ArrayList<>(java.util.Arrays.asList(arrayQuaternion));

        // moveRobot(trajectory, orient);
    }

    @Override
    protected void runPlan3(){
        // write here your plan 3
    }

    public void moveRobot(java.util.ArrayList<Point> jalur, java.util.ArrayList<double[]> orientasi){
        int LOOP_MAX = 4;
        Result result;
        for (int i = 0; i < jalur.size(); i++){
            String qr_contents;
            qua_w = 0;
            qua_x = 0;
            qua_y = 0;
            qua_z = 0;

            Quaternion quat = eulerToQuaternion(orientasi.get(i));
            Point pt = jalur.get(i);

            result = api.moveTo(pt, quat, true);

            int loopCounter = 0;
            while (!result.hasSucceeded() || loopCounter < LOOP_MAX) {
                result = api.moveTo(pt, quat, true);
                ++loopCounter;
            }

            if (pt == POINT_P11){
                Bitmap bitmap = api.getBitmapNavCam();
                Log.d(TAG, "Posisi: P11");
                qr_contents = getQR(bitmap);
                api.judgeSendDiscoveredQR(0, qr_contents);
                QR_LIST.add(qr_contents);
            }
            else if (pt == POINT_P12){
                Bitmap bitmap = api.getBitmapNavCam();
                Log.d(TAG, "Posisi: P12");
                qr_contents = getQR(bitmap);
                api.judgeSendDiscoveredQR(1, qr_contents);
                QR_LIST.add(qr_contents);
            }
            else if (pt == POINT_P13){
                Bitmap bitmap = api.getBitmapNavCam();
                Log.d(TAG, "Posisi: P13");
                qr_contents = getQR(bitmap);
                api.judgeSendDiscoveredQR(2, qr_contents);
                QR_LIST.add(qr_contents);
            }
            else if (pt == POINT_P21){
                Bitmap bitmap = api.getBitmapNavCam();
                Log.d(TAG, "Posisi: P21");
                qr_contents = getQR(bitmap);
                api.judgeSendDiscoveredQR(3, qr_contents);
                QR_LIST.add(qr_contents);
            }
            else if (pt == POINT_P22){
                Bitmap bitmap = api.getBitmapNavCam();
                Log.d(TAG, "Posisi: P22");
                qr_contents = getQR(bitmap);
                api.judgeSendDiscoveredQR(4, qr_contents);
                QR_LIST.add(qr_contents);
            }
            else if (pt == POINT_P23){
                Bitmap bitmap = api.getBitmapNavCam();
                Log.d(TAG, "Posisi: P23");
                qr_contents = getQR(bitmap);
                api.judgeSendDiscoveredQR(5, qr_contents);
                QR_LIST.add(qr_contents);
            }
        }
    }


    public Quaternion eulerToQuaternion(double[] rpy){
        double roll, pitch, yaw;
        roll = Math.toRadians(rpy[0]);
        pitch = Math.toRadians(rpy[1]);
        yaw = Math.toRadians(rpy[2]);
        qua_x = Math.sin(roll / 2) * Math.cos(pitch / 2) * Math.cos(yaw / 2) - Math.cos(roll / 2) * Math.sin(pitch / 2) * Math.sin(yaw / 2);
        qua_y = Math.cos(roll / 2) * Math.sin(pitch / 2) * Math.cos(yaw / 2) + Math.sin(roll / 2) * Math.cos(pitch / 2) * Math.sin(yaw / 2);
        qua_z = Math.cos(roll / 2) * Math.cos(pitch / 2) * Math.sin(yaw / 2) - Math.sin(roll / 2) * Math.sin(pitch / 2) * Math.cos(yaw / 2);
        qua_w = Math.cos(roll / 2) * Math.cos(pitch / 2) * Math.cos(yaw / 2) + Math.sin(roll / 2) * Math.sin(pitch / 2) * Math.sin(yaw / 2);
        return new Quaternion((float)qua_x, (float)qua_y, (float)qua_z, (float)qua_w);
    }
    
    public String getQR(Bitmap b){        
        String contents;
        int width = b.getWidth();
        int height = b.getHeight();
        Log.d(TAG, "Bitmap width: " + width);
        Log.d(TAG, "Bitmap height: " + height);
        int[] intArray = new int[width * height];
        b.getPixels(intArray, 0, width, 0, 0, width, height);
        LuminanceSource source = new RGBLuminanceSource(width, height, intArray);
        BinaryBitmap binarybitmap = new BinaryBitmap(new HybridBinarizer(source));
        Reader reader = new MultiFormatReader();
        com.google.zxing.Result result_qr = null;

        try {
            result_qr = reader.decode(binarybitmap);
        } catch (Exception e) {
            Log.d(TAG, "QR Code: Error decoding barcode.");
            contents = "";
        }

        contents = result_qr.getText();        
        if (contents.length() > 0) {
            Log.d(TAG, "Posisi P3: " + contents);
        }
        else {
            Log.d(TAG, "QR Code: Error decoding barcode!!!!!");
        }
        return contents;
    }
}

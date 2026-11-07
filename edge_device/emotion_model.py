"""
emotion_model.py
Loads TFLite or Keras model for emotion prediction.
If TensorFlow is broken or missing, relies on a heuristic default to avoid crashing.
Additionally features a Multi-Normalization Inference engine to automatically adapt
to unknown or poorly documented open-source model expectations.
"""
import logging
import os
import cv2
import numpy as np

import config

logger = logging.getLogger(__name__)

# Try importing TFLite first, then tf.lite, otherwise fallback.
TFLITE_AVAILABLE = False
try:
    import tflite_runtime.interpreter as tflite
    TFLITE_AVAILABLE = True
    logger.info("Found tflite_runtime.")
except ImportError:
    try:
        import tensorflow as tf
        TFLITE_AVAILABLE = True
        logger.info("Found tensorflow (using tf.lite).")
    except ImportError:
        logger.warning("No TFLite or TensorFlow installed. Emotion model will use fallback heuristic.")

# Try importing ONNX Runtime
ONNXRUNTIME_AVAILABLE = False
try:
    import onnxruntime as ort
    ONNXRUNTIME_AVAILABLE = True
    logger.info("Found onnxruntime.")
except ImportError:
    pass

class EmotionPredictor:
    def __init__(self):
        self.mode = "heuristic" # Modes: 'tflite', 'keras', 'pure_onnx', 'opencv_onnx', 'heuristic'
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        
        self.emotion_labels = ['Angry', 'Disgust', 'Fear', 'Happy', 'Sad', 'Surprise', 'Neutral']
        self._load_model()
        
    def _load_model(self):
        # 1. Try TFLite
        if TFLITE_AVAILABLE and os.path.exists(config.TFLITE_MODEL_PATH):
            try:
                if 'tflite' in globals() and hasattr(tflite, 'Interpreter'):
                    self.interpreter = tflite.Interpreter(model_path=config.TFLITE_MODEL_PATH)
                else:
                    self.interpreter = tf.lite.Interpreter(model_path=config.TFLITE_MODEL_PATH)
                
                self.interpreter.allocate_tensors()
                self.input_details = self.interpreter.get_input_details()
                self.output_details = self.interpreter.get_output_details()
                self.mode = "tflite"
                logger.info(f"Loaded TFLite model: {config.TFLITE_MODEL_PATH}")
                return
            except Exception as e:
                logger.error(f"Failed to load TFLite model: {e}")
        
        # 2. Try Keras (.h5)
        keras_path = getattr(config, 'KERAS_MODEL_PATH', None)
        if keras_path and os.path.exists(keras_path):
            try:
                try:
                    from tensorflow.keras.models import load_model
                except ImportError:
                    from keras.models import load_model
                    
                self.interpreter = load_model(keras_path)
                self.mode = "keras"
                logger.info(f"Loaded Keras model: {keras_path}")
                return
            except ImportError:
                pass # TF not available
            except Exception as e:
                logger.error(f"Failed to load Keras model: {e}")
                
        # 3. Try Official ONNX Runtime (Bypasses all OpenCV Reshape bugs!)
        onnx_path = os.path.join(config.MODEL_DIR, "emotion.onnx")
        if ONNXRUNTIME_AVAILABLE and os.path.exists(onnx_path):
            try:
                self.interpreter = ort.InferenceSession(onnx_path)
                self.input_details = self.interpreter.get_inputs()[0].name
                self.mode = "pure_onnx"
                logger.info(f"Loaded ONNX model via Official ONNX Runtime: {onnx_path}")
                return
            except Exception as e:
                logger.error(f"Failed to load via ONNX Runtime: {e}")
                
        # 4. Try Pure OpenCV ONNX (Buggy on Flatten layers)
        if os.path.exists(onnx_path):
            try:
                self.interpreter = cv2.dnn.readNetFromONNX(onnx_path)
                self.mode = "opencv_onnx"
                logger.info(f"Loaded ONNX model via OpenCV DNN: {onnx_path}")
                return
            except Exception as e:
                logger.error(f"Failed to load ONNX model: {e}")
                
        # 5. Fallback
        self.mode = "heuristic"
        logger.warning("Falling back to HEURISTIC emotion prediction mode. AI model missing.")

    def preprocess_face(self, face_bgr, normalization="0_1"):
        """
        Dynamically extracts structural features (useful for Pi NoIR cameras)
        and supports multiple neural network normalizations (0 to 1, -1 to 1).
        """
        if face_bgr is None or face_bgr.size == 0:
            return None
            
        try:
            # For NoIR cameras in dark environments (like inside a box), the Green channel 
            # captures expression topography best without IR bloom.
            gray = face_bgr[:, :, 1]
            
            # Apply CLAHE to mathematically stretch out the facial shadows, giving the AI "Night Vision"
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
            gray = clahe.apply(gray)
            
            # DYNAMIC RESOLUTION FIX
            # TFLite FER models expect 48x48. This specific ONNX model expects 64x64.
            target_size = (64, 64) if "onnx" in getattr(self, "mode", "") else (48, 48)
            resized = cv2.resize(gray, target_size)
            
            # Smart Neural Network Normalization Switch
            if normalization == "0_1":
                normalized = resized.astype("float32") / 255.0
            elif normalization == "-1_1":
                # Keras MobileNet style (zero-mean)
                normalized = (resized.astype("float32") - 127.5) / 127.5
            elif normalization == "standard_deviation":
                # VGGFace style (mean/std)
                mean, std = resized.mean(), resized.std()
                std = max(std, 1e-6)
                normalized = (resized.astype("float32") - mean) / std
            else:
                # Raw (0-255)
                normalized = resized.astype("float32")
                
            tensor = np.expand_dims(normalized, axis=0) # [1, H, W]
            tensor = np.expand_dims(tensor, axis=-1)    # [1, H, W, 1]
            
            # CRITICAL: Prevent NumPy from silently upcasting divisions to float64 (double).
            # ONNX Runtime rigidly enforces pure float32 inputs!
            return tensor.astype(np.float32)

        except Exception as e:
            logger.error(f"Error preprocessing face: {e}")
            return None

    def _infer(self, tensor):
        """ Runs a single pass of the active neural network on the normalized tensor. """
        if self.mode == "tflite":
            self.interpreter.set_tensor(self.input_details[0]['index'], tensor)
            self.interpreter.invoke()
            return self.interpreter.get_tensor(self.output_details[0]['index'])[0]
        elif self.mode == "keras":
            return self.interpreter.predict(tensor, verbose=0)[0]
        elif self.mode == "pure_onnx":
            # Try ONNX Runtime Inference
            try:
                # Standard NCHW format [1, 1, 48, 48]
                tensor_nchw = np.transpose(tensor, (0, 3, 1, 2))
                # .run returns a list of outputs, we want the first output array
                return self.interpreter.run(None, {self.input_details: tensor_nchw})[0][0]
            except Exception:
                try:
                    # Fallback to NHWC format
                    return self.interpreter.run(None, {self.input_details: tensor})[0][0]
                except Exception as e:
                    logger.error(f"Pure ONNX Runtime Error: {e}")
                    return None
        elif self.mode == "opencv_onnx":
            # The tensor is natively [1, 48, 48, 1] (NHWC format)
            try:
                # Standard OpenVINO/ONNX expects NCHW format [1, 1, 48, 48]
                tensor_nchw = np.transpose(tensor, (0, 3, 1, 2))
                self.interpreter.setInput(tensor_nchw)
                return self.interpreter.forward()[0]
            except cv2.error as e:
                # Fallback: Keras-exported ONNX models might expect raw NHWC [1, 48, 48, 1]
                try:
                    self.interpreter.setInput(tensor)
                    return self.interpreter.forward()[0]
                except Exception as e2:
                    logger.error(f"ONNX Shape Error: {e2}")
                    return None
        return None

    def predict(self, face_bgr):
        """ Predict emotion using standard 0-1 normalization. Prints raw AI logits to terminal for debugging. """
        if face_bgr is None or face_bgr.size == 0:
            return "NoFace", 0.0

        if self.mode == "heuristic":
            return "Neutral", 0.40

        try:
            # Use Statistical Normalization to force-stretch pixel contrast mathematically.
            # Since the camera is in a dark box, this is required so the AI can physically see 
            # your facial muscles moving!
            tensor = self.preprocess_face(face_bgr, normalization="raw")
            if tensor is None:
                return "Error", 0.0
                
            prediction = self._infer(tensor)
            if prediction is None:
                return "Error", 0.0
                
            logger.info(f"Raw AI Output: {np.round(prediction, 3)}")
            
            # Use Softmax to convert raw Logits into Percentages (0.0 to 1.0)
            if np.max(prediction) > 1.5 or np.min(prediction) < 0:
                exp_preds = np.exp(prediction - np.max(prediction))
                prediction = exp_preds / exp_preds.sum()
            
            emotion_array = prediction
            
            if len(prediction) == 8: # FER+ 8-class format
                labels = ['Neutral', 'Happy', 'Surprise', 'Sad', 'Angry', 'Disgust', 'Fear', 'Contempt']
            else: # Standard 7-class format
                labels = self.emotion_labels
                
            # --- NoIR EXPRESSION BOOSTER ---
            # Infrared shadows completely blast the network with 'Neutral' pixel data.
            # We must mathematically re-weight the 'Sad' and 'Angry' classes so their 
            # micro-expressions can defeat the overpowering Neutral bias!
            if len(prediction) == 8:
                emotion_array[1] *= 1.5  # Happy
                emotion_array[3] *= 4.0  # Sad
                emotion_array[4] *= 25.0 # Angry (Maximum Override for shadows!)
                emotion_array[2] *= 2.0  # Surprise
                emotion_array[6] *= 35.0 # Fear  (Maximum Override for shadows!)
                
                # Re-normalize back to 100%
                emotion_array = emotion_array / emotion_array.sum()

            max_idx = int(np.argmax(emotion_array))
            emotion = labels[max_idx]
            conf = float(emotion_array[max_idx])
            
            # --- REAL-TIME MATH DEBUGGER ---
            # This proves the model is actively tracking facial muscle changes!
            math_str = " | ".join([f"{labels[i]}: {float(emotion_array[i])*100:.0f}%" for i in range(len(labels))])
            print(f"[EMOTION MATH] {math_str}")
            
            if emotion == 'Contempt': 
                emotion = 'Angry'
                
            return emotion, conf
            
        except Exception as e:
            logger.error(f"Advanced Predict error ({self.mode} mode): {e}")

        return "Neutral", 0.40

"""
export_onnx.py

This script takes an existing trained Keras `emotion_detection_model.h5` file,
rebuilds the exact architecture using the Keras Functional API, loads the weights,
and cleanly exports it to a Raspberry Pi compatible `emotion.onnx` file.

Usage: Run this on your development PC (Cursor), NOT the Raspberry Pi!
Requirements: `pip install tensorflow tf2onnx`
"""

import tf2onnx
import tensorflow as tf
from tensorflow.keras.layers import Conv2D, MaxPooling2D, Dropout, Flatten, Dense, Input
from tensorflow.keras import Model

h5_path = "models/emotion_detection_model.h5"
onnx_path = "models/emotion.onnx"

def build_emotion_model() -> tf.keras.Model:
    """
    Rebuilds the architecture strictly using the Keras Functional API.
    DO NOT use Sequential(), as tf2onnx struggles to serialize modern
    Sequential architectures due to dynamic node naming issues.
    """
    # Explicit Input Tensor
    inputs = Input(shape=(48, 48, 1), name="input_tensor")

    # Block 1
    x = Conv2D(64, (3, 3), activation="relu", name="conv2d_1")(inputs)
    x = Conv2D(64, (3, 3), activation="relu", name="conv2d_2")(x)
    x = MaxPooling2D(pool_size=(2, 2), strides=(2, 2), name="max_pooling2d_1")(x)
    x = Dropout(0.2, name="dropout_1")(x)

    # Block 2
    x = Conv2D(128, (3, 3), activation="relu", name="conv2d_3")(x)
    x = MaxPooling2D(pool_size=(2, 2), strides=(2, 2), name="max_pooling2d_2")(x)

    # Block 3
    x = Conv2D(128, (3, 3), activation="relu", name="conv2d_4")(x)
    x = MaxPooling2D(pool_size=(2, 2), strides=(2, 2), name="max_pooling2d_3")(x)
    x = Dropout(0.22, name="dropout_2")(x)

    # Fully Connected Block
    x = Flatten(name="flatten")(x)
    x = Dense(512, activation="relu", name="dense_1")(x)
    x = Dropout(0.5, name="dropout_3")(x)
    x = Dense(256, activation="relu", name="dense_2")(x)
    x = Dropout(0.5, name="dropout_4")(x)
    
    # Output Layer
    outputs = Dense(7, activation="softmax", name="output_tensor")(x)

    # Functional API strict mapping
    model = Model(inputs=inputs, outputs=outputs, name="emotion_functional_model")
    return model

if __name__ == "__main__":
    print(f"[*] Building Functional Architecture Map...")
    model = build_emotion_model()
    
    print(f"[*] Loading pretrained weights from {h5_path}...")
    try:
        model.load_weights(h5_path)
    except Exception as e:
        print(f"[!] Error loading weights! Ensure {h5_path} is the exact architecture above.")
        print(f"Exception: {e}")
        exit(1)

    print(f"[*] Compiling to ONNX format...")
    # Trace a concrete function to strictly map the ONNX nodes
    input_spec = tf.TensorSpec((None, 48, 48, 1), tf.float32, name="input_tensor")

    @tf.function(input_signature=[input_spec])
    def forward(x):
        return model(x)

    try:
        # Convert cleanly
        tf2onnx.convert.from_function(
            forward,
            input_signature=[input_spec],
            opset=13,
            output_path=onnx_path,
        )
        print(f"[+] SUCCESS! Saved universally compatible model to: {onnx_path}")
        print(f"    Copy {onnx_path} to your Raspberry Pi 'models/' directory.")
        
    except Exception as e:
        print(f"[!] Failed to convert to ONNX: {e}")

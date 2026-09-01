import os
import sys

def check_and_guide():
    model_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../models"))
    model_path = os.path.join(model_dir, "paligemma.onnx")
    
    if not os.path.exists(model_dir):
        os.makedirs(model_dir)
        
    if os.path.exists(model_path):
        print(f"✅ PaliGemma ONNX model found at {model_path}")
    else:
        print(f"❌ PaliGemma ONNX model NOT found.")
        print("\nTo use the Cascaded AI Pipeline, you need a PaliGemma ONNX model.")
        print("You can export it from Hugging Face using the following command (requires optimum library):")
        print("pip install optimum[exporters]")
        print("optimum-cli export onnx --model google/paligemma-3b-pt-224 backend/models/paligemma.onnx --task image-to-text")
        print("\nAlternatively, place your existing paligemma.onnx file in the backend/models/ directory.")

if __name__ == "__main__":
    check_and_guide()

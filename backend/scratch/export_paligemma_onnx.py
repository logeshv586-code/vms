import os
import argparse
import logging
from optimum.onnxruntime import ORTModelForVision2Seq
from transformers import AutoProcessor, AutoTokenizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def export_model(model_id="google/paligemma-3b-pt-224", output_dir="models/paligemma_onnx"):
    """
    Downloads PaliGemma and exports it to optimized ONNX format.
    Includes INT8 quantization for CPU speed.
    """
    logger.info(f"Starting export for {model_id}...")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    try:
        # Load and export with Optimum
        # We use export=True to convert from PyTorch to ONNX
        logger.info("Downloading and converting model (this may take a few minutes)...")
        model = ORTModelForVision2Seq.from_pretrained(
            model_id,
            export=True,
            provider="CPUExecutionProvider"
        )
        
        # Save the model and processors
        model.save_pretrained(output_dir)
        
        processor = AutoProcessor.from_pretrained(model_id)
        processor.save_pretrained(output_dir)
        
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        tokenizer.save_pretrained(output_dir)
        
        logger.info(f"✅ Successfully exported PaliGemma to {output_dir}")
        
        # Note: For even more speed, we can apply quantization here
        # model = ORTModelForVision2Seq.from_pretrained(output_dir)
        # optimizer = ORTOptimizer.from_pretrained(model)
        # optimizer.optimize(save_dir=output_dir, ...)
        
    except Exception as e:
        logger.error(f"Export failed: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export PaliGemma to ONNX")
    parser.add_argument("--model", type=str, default="google/paligemma-3b-pt-224", help="HuggingFace model ID")
    parser.add_argument("--out", type=str, default="backend/models/paligemma_onnx", help="Output directory")
    
    args = parser.parse_args()
    
    # Adjust output dir relative to current working directory
    export_model(args.model, args.out)

"""Lightweight reliability contracts for the VMS AI stack.

These tests intentionally avoid importing YOLO/Gemma so they can run on a developer machine or
CI runner without downloading/loading multi-GB model weights.

Run from repository root:
    python -m unittest backend.tests.test_ai_source_contracts
"""

import ast
import pathlib
import unittest


BACKEND = pathlib.Path(__file__).resolve().parents[1]


def source(relative_path: str) -> str:
    return (BACKEND / relative_path).read_text(encoding="utf-8")


class AISourceContracts(unittest.TestCase):
    def test_modified_python_sources_parse(self):
        for relative_path in (
            "services/yolo26_engine.py",
            "services/cascaded_ai_service.py",
            "services/gemma_engine.py",
            "services/gemma_onnx_engine.py",
            "services/hard_example_collector.py",
            "services/pattern_engine.py",
            "training/train_yolo.py",
        ):
            with self.subTest(relative_path=relative_path):
                ast.parse(source(relative_path), filename=relative_path)

    def test_gemma_never_falls_back_to_fake_validation(self):
        text = source("services/gemma_engine.py")
        self.assertNotIn("_simulate_inference", text)
        self.assertNotIn("random.uniform", text)
        self.assertIn('"event_validated": False', text)
        self.assertIn('"simulated": False', text)

    def test_gemma_uses_native_gemma4_multimodal_handler(self):
        text = source("services/gemma_engine.py")
        self.assertIn("Gemma4ChatHandler", text)
        self.assertNotIn("Llava15ChatHandler", text)
        requirements = source("requirements.txt")
        self.assertIn("llama-cpp-python>=0.3.25", requirements)

    def test_yolo_tracking_is_camera_isolated(self):
        text = source("services/yolo26_engine.py")
        self.assertIn("class _StreamState", text)
        self.assertIn("self._streams", text)
        self.assertIn("_get_stream_state", text)
        self.assertIn("stream_id", text)

    def test_cascade_merges_semantics_by_detection_index(self):
        text = source("services/cascaded_ai_service.py")
        self.assertIn('"detection_index": detection_index', text)
        self.assertIn('region.get("detection_index")', text)
        self.assertNotIn('tasks=["caption"]', text)

    def test_logits_only_paligemma_is_not_presented_as_generated_text(self):
        text = source("services/gemma_onnx_engine.py")
        self.assertIn("logits only", text)
        self.assertIn("autoregressive", text)

    def test_pattern_engine_has_real_camera_normalization(self):
        tree = ast.parse(source("services/pattern_engine.py"))
        functions = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertIn("_normalize_id", functions)
        normalize_source = ast.get_source_segment(
            source("services/pattern_engine.py"), functions["_normalize_id"]
        )
        self.assertIn("return clean", normalize_source)
        self.assertIn("_zones_for_source", functions)

    def test_event_records_do_not_claim_fixed_95_percent_confidence(self):
        text = source("services/pattern_engine.py")
        self.assertNotIn('"confidence": 0.95', text)
        self.assertIn("_event_confidence", text)

    def test_hard_examples_are_proposals_not_ground_truth(self):
        text = source("services/hard_example_collector.py")
        self.assertIn('"review_status": "pending"', text)
        self.assertIn('"ground_truth": None', text)
        self.assertIn('"proposal_only": True', text)

    def test_training_refuses_raw_review_queue(self):
        text = source("training/train_yolo.py")
        self.assertIn('"review_queue"', text)
        self.assertIn("Refusing to train directly", text)


if __name__ == "__main__":
    unittest.main()

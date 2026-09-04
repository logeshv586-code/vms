"""Lightweight reliability contracts for the VMS AI stack.

These tests intentionally avoid importing YOLO/Gemma so they can run on a developer machine or
CI runner without downloading/loading multi-GB model weights.

Run from repository root:
    python -m unittest backend.tests.test_ai_source_contracts
"""

import ast
import json
import pathlib
import unittest


BACKEND = pathlib.Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent


def source(relative_path: str) -> str:
    return (BACKEND / relative_path).read_text(encoding="utf-8")


def root_source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class AISourceContracts(unittest.TestCase):
    def test_modified_python_sources_parse(self):
        for relative_path in (
            "main.py",
            "main_legacy.py",
            "services/yolo26_engine.py",
            "services/cascaded_ai_service.py",
            "services/gemma_engine.py",
            "services/gemma_onnx_engine.py",
            "services/hard_example_collector.py",
            "services/pattern_engine.py",
            "services/security_runtime.py",
            "services/camera_ai_preferences.py",
            "services/event_evidence.py",
            "routes/camera_ai.py",
            "routes/camera_rules.py",
            "routes/camera_zones.py",
            "routes/vehicle_monitoring.py",
            "tools/validate_runtime.py",
            "training/train_yolo.py",
            "training/calibrate_face_threshold.py",
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

    def test_webrtc_crypto_stack_is_compatible_with_current_aiortc(self):
        requirements = source("requirements.txt")
        self.assertIn("aiortc>=1.15.0,<1.16.0", requirements)
        self.assertIn("av>=14.0.0,<18.0.0", requirements)
        self.assertIn("cryptography>=44.0.0,<51.0.0", requirements)
        self.assertIn("pyOpenSSL>=25.0.0,<27.0.0", requirements)

    def test_yolo_tracking_is_camera_isolated(self):
        text = source("services/yolo26_engine.py")
        self.assertIn("class _StreamState", text)
        self.assertIn("self._streams", text)
        self.assertIn("_get_stream_state", text)
        self.assertIn("stream_id", text)
        self.assertIn("tracker_name", text)

    def test_detection_contract_is_canonical_and_backwards_compatible(self):
        text = source("services/yolo26_engine.py")
        for field in (
            '"track_id"',
            '"class_name"',
            '"bbox"',
            '"centroid"',
            '"norm_bbox"',
            '"norm_centroid"',
            '"schema_version": "vms-detection-1"',
        ):
            self.assertIn(field, text)
        self.assertIn('"box": bbox', text)
        self.assertIn('"label": label', text)
        self.assertIn('"id": track_id', text)
        self.assertIn('"class": label', text)

    def test_cascade_merges_semantics_by_detection_index(self):
        text = source("services/cascaded_ai_service.py")
        self.assertIn('"detection_index": detection_index', text)
        self.assertIn('region.get("detection_index")', text)
        self.assertIn('detection.get("class_name")', text)
        self.assertIn('detection.get("track_id", detection.get("id"))', text)
        self.assertNotIn('tasks=["caption"]', text)

    def test_hard_examples_are_collected_after_tier2(self):
        text = source("services/cascaded_ai_service.py")
        tier2_position = text.rfind('metadata["tier2_error_count"] = tier2_errors')
        collector_position = text.rfind("self._collect_hard_example(frame, metadata, stream_id)")
        self.assertGreater(tier2_position, -1)
        self.assertGreater(collector_position, tier2_position)

    def test_logits_only_paligemma_is_not_presented_as_generated_text(self):
        text = source("services/gemma_onnx_engine.py")
        self.assertIn("logits only", text)
        self.assertIn("autoregressive", text)

    def test_pattern_engine_has_real_camera_normalization(self):
        text = source("services/pattern_engine.py")
        tree = ast.parse(text)
        functions = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertIn("_normalize_id", functions)
        normalize_source = ast.get_source_segment(text, functions["_normalize_id"])
        self.assertIn("return clean", normalize_source)
        self.assertIn("_zones_for_source", functions)

    def test_event_records_do_not_claim_fixed_95_percent_confidence(self):
        text = source("services/pattern_engine.py")
        self.assertNotIn('"confidence": 0.95', text)
        self.assertIn("_event_confidence", text)

    def test_hard_examples_are_proposals_not_ground_truth_and_bounded(self):
        text = source("services/hard_example_collector.py")
        self.assertIn('"review_status": "pending"', text)
        self.assertIn('"ground_truth": None', text)
        self.assertIn('"proposal_only": True', text)
        self.assertIn("VMS_HARD_EXAMPLE_RETENTION_DAYS", text)
        self.assertIn("VMS_HARD_EXAMPLE_MAX_STORAGE_GB", text)
        self.assertIn("_cleanup_if_due", text)

    def test_face_identity_never_auto_registers(self):
        text = source("detections/face_recognition.py")
        self.assertIn("self.auto_register = False", text)
        self.assertIn('"auto_register": False', text)
        self.assertNotIn("cv2.calcHist", text)

    def test_security_bootstrap_redacts_logs_json_and_wildcard_cors(self):
        runtime = source("services/security_runtime.py")
        bootstrap = source("services/__init__.py")
        self.assertIn("install_log_redaction", bootstrap)
        self.assertIn("install_json_redaction", bootstrap)
        self.assertIn("install_cors_guard", bootstrap)
        self.assertIn("VMS_CORS_ORIGINS", runtime)
        self.assertIn("sanitize_payload", runtime)
        self.assertIn("CORSMiddleware.__init__ = secure_init", runtime)
        self.assertIn("JSONResponse.render = secure_render", runtime)

    def test_electron_does_not_log_camera_configuration_or_raw_vlc_url(self):
        text = root_source("main.js")
        self.assertIn("redactUrlForLog(trimmedUrl)", text)
        self.assertNotIn("Saving camera configuration to file:", text)
        self.assertNotIn("args.join(' ')", text)

    def test_frontend_has_one_canonical_event_service(self):
        canonical = root_source("src/services/eventService.js")
        shim = root_source("src/services/eventsService.js")
        self.assertIn("export const fetchEventRules", canonical)
        self.assertIn("from './eventService'", shim)
        self.assertNotIn("apiRequest", shim)

    def test_training_refuses_raw_review_queue(self):
        text = source("training/train_yolo.py")
        self.assertIn('"review_queue"', text)
        self.assertIn("Refusing to train directly", text)

    def test_runtime_validation_and_face_calibration_require_real_evidence(self):
        runtime = source("tools/validate_runtime.py")
        calibration = source("training/calibrate_face_threshold.py")
        self.assertIn("nvidia-smi", runtime)
        self.assertIn("observed_streams", runtime)
        self.assertIn("same_identity", calibration)
        self.assertIn("false_accept_rate", calibration)

    def test_runtime_forces_stable_configured_stream_identity(self):
        text = source("main.py")
        self.assertIn("class HardenedRTSPStream", text)
        self.assertIn("resolved_stream_id = stream_id or _infer_stream_id(rtsp_url)", text)
        self.assertIn("A stable stream_id is required", text)
        self.assertIn("legacy.RTSPStream = HardenedRTSPStream", text)

    def test_persisted_rules_drive_24x7_ai_independent_of_viewer(self):
        runtime = source("main.py")
        camera_rules = source("routes/camera_rules.py")
        self.assertIn('monitoring_enabled = bool(preferences.get("enabled", True)) and bool(active_rule_ids)', runtime)
        self.assertIn("Viewer detached; 24/7 AI monitoring continues", runtime)
        self.assertIn("set_camera_ai_enabled(camera_id, bool(requested_rule_ids))", camera_rules)
        self.assertIn("event_evidence_service.register_frame", runtime)

    def test_deterministic_events_are_dispatched_only_by_pattern_engine(self):
        runtime = source("main.py")
        tree = ast.parse(runtime)
        method = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_ai_processing_loop"
        )
        method_text = ast.get_source_segment(runtime, method)
        self.assertNotIn(".trigger_alert_api(", method_text)
        self.assertIn("PatternEngine already persists deterministic", method_text)

    def test_event_evidence_is_annotated_buffered_and_validated(self):
        text = source("services/event_evidence.py")
        self.assertIn("class EventEvidenceService", text)
        self.assertIn("self._buffers", text)
        self.assertIn("pin_candidate", text)
        self.assertIn("evidence_pre_seconds", text)
        self.assertIn("evidence_post_seconds", text)
        self.assertIn("cv2.VideoWriter", text)
        self.assertIn("_validate_video", text)
        self.assertIn('"detection_snapshot"', text)
        self.assertNotIn("-rtsp_transport", text)

    def test_pattern_proof_callback_is_replaced_by_annotated_evidence(self):
        runtime = source("main.py")
        self.assertIn("legacy.pattern_engine._start_proof_recording = _start_annotated_proof", runtime)
        self.assertIn("event_evidence_service.start_event(event_id, source_id, event)", runtime)

    def test_camera_ai_preferences_are_atomic_and_camera_specific(self):
        text = source("services/camera_ai_preferences.py")
        self.assertIn("normalize_camera_id", text)
        self.assertIn("os.replace", text)
        self.assertIn('"confidence": None', text)
        self.assertIn('"iou": None', text)
        self.assertIn('"tracker": None', text)
        self.assertIn('"ai_fps": 4.0', text)

    def test_camera_rule_zone_and_settings_writes_are_atomic(self):
        for relative_path in (
            "routes/camera_rules.py",
            "routes/camera_zones.py",
            "services/camera_settings.py",
        ):
            with self.subTest(relative_path=relative_path):
                text = source(relative_path)
                self.assertIn("os.replace", text)
                self.assertIn("threading.RLock", text)

    def test_vehicle_monitoring_authoritative_config_is_enabled(self):
        config = json.loads(root_source("events_configuration.json"))
        rule = next(item for item in config["rules"] if item["id"] == 22)
        self.assertEqual(rule["name"], "Vehicle Monitoring")
        self.assertTrue(rule["enabled"])

    def test_vehicle_monitoring_uses_real_lazy_alpr_and_central_events(self):
        text = source("routes/vehicle_monitoring.py")
        self.assertIn("def _lazy_init_alpr", text)
        self.assertIn("from sort.sort import Sort as _Sort", text)
        self.assertNotIn("mock tracker", text.lower())
        self.assertIn("util_get_car(plate_detection, track_ids)", text)
        self.assertIn("util_read_license_plate(threshold)", text)
        self.assertIn("pattern_engine.trigger_alert_api(", text)
        self.assertIn('"type": "Vehicle Monitoring"', text)
        self.assertIn("os.replace(temp_path, self._events_file)", text)
        self.assertIn("A configured stable stream_id is required", text)

    def test_ai_detection_panel_has_center_point_overlay(self):
        wrapper = root_source("src/components/events/AIDetectionTab.js")
        self.assertIn("norm_centroid", wrapper)
        self.assertIn("det.centroid || det.center", wrapper)
        self.assertIn("<circle", wrapper)
        self.assertIn("LegacyAIDetectionTab", wrapper)


if __name__ == "__main__":
    unittest.main()

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
ROOT = BACKEND.parent


def source(relative_path: str) -> str:
    return (BACKEND / relative_path).read_text(encoding="utf-8")


def root_source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class AISourceContracts(unittest.TestCase):
    def test_modified_python_sources_parse(self):
        for relative_path in (
            "services/yolo26_engine.py",
            "services/cascaded_ai_service.py",
            "services/gemma_engine.py",
            "services/gemma_onnx_engine.py",
            "services/hard_example_collector.py",
            "services/pattern_engine.py",
            "services/security_runtime.py",
            "routes/camera_rules.py",
            "routes/ptz.py",
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

    def test_cascade_merges_semantics_by_detection_index(self):
        text = source("services/cascaded_ai_service.py")
        self.assertIn('"detection_index": detection_index', text)
        self.assertIn('region.get("detection_index")', text)
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

    def test_detection_rule_ui_uses_effective_camera_mapping(self):
        helpers = root_source("src/utils/detectionRules.js")
        live = root_source("src/components/events/CurrentEvents.js")
        search = root_source("src/components/events/SearchEvents.js")
        camera_table = root_source("src/components/events/CameraRuleTable.js")
        self.assertEqual(helpers.count("{ id:"), 23)
        self.assertIn("getRulesForCamera", helpers)
        self.assertIn("eventMatchesCamera", helpers)
        self.assertIn("getRulesForCamera", live)
        self.assertIn("eventMatchesCamera", live)
        self.assertIn("Date Range", search)
        self.assertIn("eventMatchesCamera", search)
        self.assertIn("camera-rule-state", camera_table)
        self.assertIn("onCameraSelect(camera.id)", camera_table)

    def test_camera_rule_writes_are_atomic_and_alias_aware(self):
        text = source("routes/camera_rules.py")
        self.assertIn("_CAMERA_RULES_LOCK", text)
        self.assertIn("os.replace", text)
        self.assertIn("_expanded_camera_rules", text)
        self.assertIn("globalEnabledRuleIds", text)
        self.assertIn("router.include_router(ptz_router)", text)

    def test_ptz_is_real_onvif_probe_and_fail_closed(self):
        text = source("routes/ptz.py")
        self.assertIn("ONVIFCamera", text)
        self.assertIn("create_ptz_service", text)
        self.assertIn("GetPresets", text)
        self.assertIn("GotoPreset", text)
        self.assertIn("ContinuousMove", text)
        self.assertIn('"verified": False', text)
        self.assertIn("credentials", text.lower())
        self.assertNotIn('"password": camera_meta', text)

    def test_ptz_menu_no_longer_falls_back_to_current_events(self):
        content = root_source("src/components/events/EventsContent.js")
        tour = root_source("src/components/events/PTZAutoTour.js")
        track = root_source("src/components/events/PTZAutoTrack.js")
        self.assertIn("case 'ptz-auto-tour'", content)
        self.assertIn("case 'ptz-auto-track'", content)
        self.assertIn("Test PTZ & Load Presets", tour)
        self.assertIn("Save & Arm Controller", track)
        self.assertIn("live handoff", track.lower())

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


if __name__ == "__main__":
    unittest.main()

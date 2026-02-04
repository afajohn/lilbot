#!/usr/bin/env python
"""Simple import validation test for playwright_runner refactoring."""

import sys

try:
    from tools.qa.playwright_runner import (
        run_analysis,
        run_analysis_batch,
        set_max_concurrent_contexts,
        get_max_concurrent_contexts,
        PlaywrightPool,
        PlaywrightEventLoopThread,
        BatchAnalysisRequest
    )
    
    print("SUCCESS: All imports successful")
    print(f"SUCCESS: Max concurrent contexts default: {get_max_concurrent_contexts()}")
    
    # Test configuration
    set_max_concurrent_contexts(2)
    print(f"SUCCESS: Set max concurrent contexts to: {get_max_concurrent_contexts()}")
    
    # Verify new functions exist
    assert callable(run_analysis_batch), "run_analysis_batch should be callable"
    print("SUCCESS: run_analysis_batch is callable")
    
    assert callable(set_max_concurrent_contexts), "set_max_concurrent_contexts should be callable"
    print("SUCCESS: set_max_concurrent_contexts is callable")
    
    # Verify BatchAnalysisRequest exists and is a dataclass
    from dataclasses import is_dataclass
    assert is_dataclass(BatchAnalysisRequest), "BatchAnalysisRequest should be a dataclass"
    print("SUCCESS: BatchAnalysisRequest is a dataclass")
    
    print("\nAll validation checks passed!")
    sys.exit(0)
    
except Exception as e:
    print(f"FAILED: Import validation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

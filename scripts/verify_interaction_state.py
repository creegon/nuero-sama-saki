
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.interaction_state import get_interaction_state, InteractionMode

def test_interaction_state():
    print("=== Testing Interaction State ===")
    state = get_interaction_state()
    
    # 1. Test Initial State
    print(f"Initial Score: {state.engagement_score} (Expected ~50)")
    print(f"Initial Mode : {state.mode} (Expected NORMAL)")
    
    # 2. Test Boost
    print("\n[Action] User speaks (Boost +10)...")
    state.update_activity(boost=10)
    print(f"Score after boost: {state.engagement_score} (Expected ~60)")
    
    # 3. Test High Engagement Transition
    print("\n[Action] Boosting to >80...")
    state.update_activity(boost=30) 
    print(f"Score: {state.engagement_score}")
    print(f"Mode : {state.mode} (Expected HIGH_ENGAGEMENT)")
    
    # 4. Test Decay
    print("\n[Action] Decaying...")
    state.decay_score(amount=50)
    print(f"Score after decay: {state.engagement_score}")
    print(f"Mode : {state.mode} (Expected NORMAL)")
    
    # 5. Test Busy Mode
    print("\n[Action] Setting Busy Mode (60 min)...")
    state.set_busy(60)
    print(f"Mode : {state.mode} (Expected BUSY)")
    print(f"Score: {state.engagement_score} (Expected low)")
    
    # 6. Test Interval Calculation
    interval = state.get_next_interval()
    print(f"Next Interval (Busy): {interval}s (Expected large)")
    
    print("\n[Action] Setting Normal...")
    state.set_normal()
    print(f"Mode : {state.mode} (Expected NORMAL)")
    
    # Test Interval for Normal High Score vs Low Score
    state.engagement_score = 100
    int_high = state.get_next_interval()
    print(f"Interval (Score 100): {int_high}s")
    
    state.engagement_score = 0
    int_low = state.get_next_interval()
    print(f"Interval (Score 0): {int_low}s")
    
    
    if int_high < int_low:
        print("[Pass] Logic Correct: Higher score = Shorter interval")
    else:
        print("[Fail] Logic Error: Higher score should have shorter interval")

    print("\n=== Verifying ResponseHandler syntax ===")
    try:
        from core.response_handler import ResponseHandler
        print("ResponseHandler imported successfully.")
    except Exception as e:
        print(f"ResponseHandler import failed: {e}")


if __name__ == "__main__":
    test_interaction_state()

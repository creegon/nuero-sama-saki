
try:
    from voxcpm.core import VoxCPM
    import inspect
    print("VoxCPM.generate_streaming signature:")
    print(inspect.signature(VoxCPM.generate_streaming))
    
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Error: {e}")

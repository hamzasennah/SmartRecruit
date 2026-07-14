try:
    import torch
except ImportError:
    print("torch n'est pas installe.")
else:
    print(f"CUDA disponible: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")


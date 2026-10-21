import importlib.metadata as m
for p in ['torch','transformers','peft','trl','unsloth','bitsandbytes','datasets','accelerate','chess','fastapi']:
    try: print(p, m.version(p))
    except Exception as e: print(p, 'MISSING')
import torch;print('cuda',torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')

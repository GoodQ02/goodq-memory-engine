import yaml

with open('config.yaml', 'r') as f:
    cfg = yaml.safe_load(f)

print("Scene Detection Settings:")
print(f"  threshold: {cfg['video']['scene_detection']['threshold']}")
print(f"  min_scene_len_sec: {cfg['video']['scene_detection']['min_scene_len_sec']}")
print(f"  adaptive: {cfg['video']['scene_detection']['adaptive']}")

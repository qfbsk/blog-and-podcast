import os
import json
import subprocess
import datetime
import glob

# 读取订阅列表
with open('scripts/subscriptions.json', 'r') as f:
    subscriptions = json.load(f)

# 创建输出目录
os.makedirs('videos', exist_ok=True)
os.makedirs('covers', exist_ok=True)
os.makedirs('metadata', exist_ok=True)

# 获取当天序列号
def get_today_sequence():
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    existing = glob.glob(f'videos/{date_str}_*.mp4')
    return len(existing) + 1

# 处理每个订阅源
current_date = datetime.datetime.now().strftime("%Y%m%d")
sequence = get_today_sequence()

for sub in subscriptions:
    try:
        # 获取RSS源数据
        cmd = f"curl -s '{sub['url']}'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        rss_data = json.loads(result.stdout)
        
        # 只处理最新一条视频
        if not rss_data['items']:
            continue
            
        latest_item = rss_data['items'][0]
        
        # 设置文件名
        file_prefix = f"{current_date}_{str(sequence).zfill(2)}"
        sequence += 1
        
        # 设置下载质量
        quality = f"best[height<={sub['quality']}]" if isinstance(sub['quality'], int) else "best"
        
        # 下载视频
        video_cmd = [
            'python', 'clean-ytdlp/yt_dlp/__main__.py',
            '-f', quality,
            '-o', f'videos/{file_prefix}.%(ext)s',
            '--write-thumbnail',
            '--convert-thumbnails', 'jpg',
            '--no-check-certificate',
            latest_item['url'] or latest_item['link']
        ]
        subprocess.run(video_cmd, check=True)
        
        # 生成元数据
        metadata = {
            "id": file_prefix,
            "title": latest_item['title'],
            "description": latest_item.get('content', latest_item.get('summary', '')),
            "cover": f"{file_prefix}_cover.jpg",
            "video": f"{file_prefix}.mp4",
            "source": sub['type'],
            "source_name": sub['name'],
            "original_link": latest_item['url'] or latest_item['link'],
            "date": datetime.datetime.now().isoformat()
        }
        
        # 保存封面文件
        for ext in ['jpg', 'webp', 'png']:
            cover_src = f"videos/{file_prefix}.{ext}"
            if os.path.exists(cover_src):
                os.rename(cover_src, f"covers/{file_prefix}_cover.jpg")
                break
        
        print(f"成功处理: {sub['name']}")
        
    except Exception as e:
        print(f"处理失败 {sub['name']}: {str(e)}")

# 生成当天的总元数据文件
all_metadata = {
    "date": current_date,
    "videos": []
}

for file in os.listdir('metadata'):
    if file.endswith('.json'):
        with open(f'metadata/{file}', 'r') as f:
            video_data = json.load(f)
            all_metadata["videos"].append(video_data)

with open(f'metadata/{current_date}.json', 'w') as f:
    json.dump(all_metadata, f, indent=2)
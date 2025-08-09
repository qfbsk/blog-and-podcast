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
        print(f"\n处理订阅源: {sub['name']}")
        print(f"URL: {sub['url']}?format=json")
        
        # 获取RSS源数据（添加format=json参数）
        cmd = f"curl -s '{sub['url']}?format=json'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        # 调试输出
        print(f"状态码: {result.returncode}")
        print(f"输出长度: {len(result.stdout)}")
        print(f"错误信息: {result.stderr}")
        
        if result.returncode != 0 or len(result.stdout) < 10:
            print("获取RSS数据失败")
            continue
        
        try:
            rss_data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {str(e)}")
            # 打印前200个字符帮助调试
            print("响应内容前200字符:", result.stdout[:200])
            continue
        
        # 只处理最新一条视频
        if not rss_data['items']:
            print("没有找到视频项目")
            continue
            
        latest_item = rss_data['items'][0]
        print(f"找到视频: {latest_item['title']}")
        
        # 设置文件名
        file_prefix = f"{current_date}_{str(sequence).zfill(2)}"
        sequence += 1
        
        # 设置下载质量
        quality = f"best[height<={sub['quality']}]" if isinstance(sub['quality'], int) else "best"
        print(f"下载质量: {quality}")
        
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
        print("执行命令:", " ".join(video_cmd))
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
        cover_found = False
        for ext in ['jpg', 'webp', 'png']:
            cover_src = f"videos/{file_prefix}.{ext}"
            if os.path.exists(cover_src):
                os.rename(cover_src, f"covers/{file_prefix}_cover.jpg")
                cover_found = True
                break
        
        if not cover_found:
            print("警告: 未找到封面文件")
        
        # 保存单个视频元数据
        with open(f'metadata/{file_prefix}.json', 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"成功处理: {sub['name']}")
        
    except Exception as e:
        print(f"处理失败 {sub['name']}: {str(e)}")

# 生成当天的总元数据文件
all_metadata = {
    "date": current_date,
    "videos": []
}

for file in os.listdir('metadata'):
    if file.endswith('.json') and file.startswith(current_date):
        try:
            with open(f'metadata/{file}', 'r') as f:
                video_data = json.load(f)
                all_metadata["videos"].append(video_data)
        except:
            continue

with open(f'metadata/{current_date}.json', 'w') as f:
    json.dump(all_metadata, f, indent=2)
    print(f"生成总元数据文件: metadata/{current_date}.json")

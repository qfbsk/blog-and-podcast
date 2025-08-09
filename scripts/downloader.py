import os
import json
import subprocess
import datetime
import glob
import time
import re

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
        print(f"\n===== 处理订阅源: {sub['name']} =====")
        print(f"URL: {sub['url']}")
        
        # 获取RSS源数据 - 添加User-Agent和重试机制
        cmd = f"curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36' --max-time 30 '{sub['url']}'"
        print(f"执行命令: {cmd}")
        
        max_retries = 3
        retry_count = 0
        result = None
        
        while retry_count < max_retries:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            # 调试输出
            print(f"状态码: {result.returncode}")
            print(f"输出长度: {len(result.stdout)}")
            print(f"错误信息: {result.stderr}")
            
            # 检查是否成功
            if (result.returncode == 0 and 
                len(result.stdout) > 100 and 
                "<!DOCTYPE html>" not in result.stdout and
                "error" not in result.stdout.lower()):
                break
                
            retry_count += 1
            print(f"请求失败，重试 {retry_count}/{max_retries}")
            time.sleep(5)
        
        # 最终检查
        if (result.returncode != 0 or 
            len(result.stdout) < 100 or 
            "<!DOCTYPE html>" in result.stdout or
            "error" in result.stdout.lower()):
            print(f"❌ 获取RSS数据失败: {sub['name']}")
            print("响应内容前200字符:", result.stdout[:200])
            continue
        
        try:
            rss_data = json.loads(result.stdout)
            print(f"✅ 成功解析JSON数据，找到 {len(rss_data.get('items', []))} 个项目")
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析失败: {str(e)}")
            print("响应内容前200字符:", result.stdout[:200])
            continue
        
        # 只处理最新一条视频
        if not rss_data.get('items'):
            print("⚠️ 没有找到视频项目")
            continue
            
        # 查找最新视频（按发布时间排序）
        latest_item = None
        for item in rss_data['items']:
            # 确保是视频类型
            if 'video' not in item.get('title', '').lower() and 'video' not in item.get('description', '').lower():
                continue
                
            if not latest_item or ('pubDate' in item and item['pubDate'] > latest_item.get('pubDate', '')):
                latest_item = item
        
        if not latest_item:
            print("⚠️ 未找到有效的视频项目")
            continue
            
        print(f"🎬 找到视频: {latest_item['title']}")
        
        # 设置文件名
        file_prefix = f"{current_date}_{str(sequence).zfill(2)}"
        sequence += 1
        
        # 设置下载质量
        quality = f"best[height<={sub['quality']}]" if isinstance(sub['quality'], int) else "best"
        print(f"📺 下载质量: {quality}")
        
        # 获取视频URL
        video_url = latest_item.get('url') or latest_item.get('link') or latest_item.get('guid')
        if not video_url:
            print("⚠️ 未找到视频URL")
            continue
            
        print(f"🔗 视频URL: {video_url}")
        
        # 下载视频
        video_cmd = [
            'yt-dlp',
            '-f', quality,
            '-o', f'videos/{file_prefix}.%(ext)s',
            '--write-thumbnail',
            '--convert-thumbnails', 'jpg',
            '--no-check-certificate',
            video_url
        ]
        print("执行下载命令:", " ".join(video_cmd))
        try:
            subprocess.run(video_cmd, check=True)
            print("✅ 视频下载成功")
        except subprocess.CalledProcessError as e:
            print(f"❌ 视频下载失败: {str(e)}")
            continue
        
        # 生成元数据
        metadata = {
            "id": file_prefix,
            "title": latest_item['title'],
            "description": latest_item.get('content', latest_item.get('summary', '')),
            "cover": f"{file_prefix}_cover.jpg",
            "video": f"{file_prefix}.mp4",
            "source": sub['type'],
            "source_name": sub['name'],
            "original_link": video_url,
            "date": datetime.datetime.now().isoformat()
        }
        
        # 保存封面文件
        cover_found = False
        for ext in ['jpg', 'webp', 'png']:
            cover_src = f"videos/{file_prefix}.{ext}"
            if os.path.exists(cover_src):
                os.rename(cover_src, f"covers/{file_prefix}_cover.jpg")
                cover_found = True
                print(f"🖼️ 封面文件已保存: covers/{file_prefix}_cover.jpg")
                break
        
        if not cover_found:
            print("⚠️ 未找到封面文件")
        
        # 保存单个视频元数据
        with open(f'metadata/{file_prefix}.json', 'w') as f:
            json.dump(metadata, f, indent=2)
            print(f"📄 元数据已保存: metadata/{file_prefix}.json")
        
        print(f"🎉 成功处理: {sub['name']}")
        
    except Exception as e:
        print(f"🔥 处理失败 {sub['name']}: {str(e)}")

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
        except Exception as e:
            print(f"⚠️ 加载元数据失败 {file}: {str(e)}")
            continue

if all_metadata["videos"]:
    with open(f'metadata/{current_date}.json', 'w') as f:
        json.dump(all_metadata, f, indent=2)
        print(f"📊 生成总元数据文件: metadata/{current_date}.json")
else:
    print("⚠️ 没有视频数据，跳过生成总元数据文件")

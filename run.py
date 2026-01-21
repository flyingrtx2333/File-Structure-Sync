import os
import hashlib
import json
import shutil
import argparse
import time

def get_fast_md5(file_path):
    """
    快速哈希：读取文件头、中、尾各 1MB 数据进行计算。
    适用于超大视频或素材文件，速度极快。
    """
    sample_size = 1024 * 1024  # 1MB
    try:
        file_size = os.path.getsize(file_path)
        hash_md = hashlib.md5()
        with open(file_path, 'rb') as f:
            if file_size <= sample_size * 3:
                hash_md.update(f.read())
            else:
                # 头部
                hash_md.update(f.read(sample_size))
                # 中部
                f.seek(file_size // 2)
                hash_md.update(f.read(sample_size))
                # 尾部
                f.seek(file_size - sample_size)
                hash_md.update(f.read(sample_size))
                # 加上文件大小防止长度相同的不同文件冲突
                hash_md.update(str(file_size).encode())
        return hash_md.hexdigest()
    except Exception as e:
        print(f"[错误] 无法计算哈希 {file_path}: {e}")
        return None

def scan_source(source_dir, output_json, log_fn=print, progress_every=10):
    """扫描源盘（使用盘），生成映射表"""
    mapping = {}
    if log_fn is None:
        log_fn = print
    log_fn(f"[*] 正在扫描源目录: {source_dir}")
    start_time = time.time()
    count = 0

    for root, _, files in os.walk(source_dir):
        for file in files:
            if file.startswith('.') or file.lower() == 'thumbs.db':
                continue
            
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, source_dir)
            
            f_hash = get_fast_md5(full_path)
            if f_hash:
                mapping[f_hash] = rel_path
                count += 1
                if progress_every and count % progress_every == 0:
                    log_fn(f" 已处理 {count} 个文件...")

    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=4)
    
    end_time = time.time()
    log_fn(f"[OK] 扫描完成！共 {count} 个文件，耗时 {end_time - start_time:.2f}s")
    log_fn(f"[OK] 映射表已保存至: {output_json}")

def sync_target(target_dir, mapping_json, dry_run=False, log_fn=print):
    """根据映射表整理目标盘（备份盘）"""
    if not os.path.exists(mapping_json):
        if log_fn is None:
            log_fn = print
        log_fn(f"[错误] 找不到映射表文件: {mapping_json}")
        return

    with open(mapping_json, 'r', encoding='utf-8') as f:
        mapping = json.load(f)

    if log_fn is None:
        log_fn = print
    log_fn(f"[*] 正在索引目标目录 (此过程可能较慢): {target_dir}")
    target_index = {}
    for root, _, files in os.walk(target_dir):
        for file in files:
            full_path = os.path.join(root, file)
            f_hash = get_fast_md5(full_path)
            if f_hash:
                target_index[f_hash] = full_path

    log_fn(f"[*] 开始匹配与结构重组...")
    if dry_run:
        log_fn("注意：当前处于 [预览模式]，不会实际移动文件。")

    moved_count = 0
    for f_hash, rel_path in mapping.items():
        if f_hash in target_index:
            old_path = target_index[f_hash]
            new_path = os.path.join(target_dir, rel_path)
            
            if os.path.abspath(old_path) == os.path.abspath(new_path):
                continue
            
            if not dry_run:
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                shutil.move(old_path, new_path)
            
            log_fn(f"[{'预览' if dry_run else '移动'}] {os.path.basename(old_path)} -> {rel_path}")
            moved_count += 1

    # 清理空文件夹
    if not dry_run:
        log_fn("[*] 正在清理空文件夹...")
        for root, dirs, _ in os.walk(target_dir, topdown=False):
            for d in dirs:
                dir_path = os.path.join(root, d)
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)

    log_fn(f"[OK] 整理完成！共处理 {moved_count} 个文件。")

def main():
    parser = argparse.ArgumentParser(description="File-Structure-Sync: 基于指纹的文件结构同步工具")
    parser.add_argument("mode", choices=["scan", "sync"], help="操作模式: scan (扫描源盘生成映射) 或 sync (同步目标盘)")
    parser.add_argument("--src", help="源目录路径 (使用盘)")
    parser.add_argument("--dst", help="目标目录路径 (备份盘)")
    parser.add_argument("--map", default="file_map.json", help="映射表文件名 (默认: file_map.json)")
    parser.add_argument("--dry-run", action="store_true", help="预览模式：仅显示将要进行的操作，不实际移动文件")

    args = parser.parse_args()

    if args.mode == "scan":
        if not args.src:
            print("错误：扫描模式需要指定 --src 参数")
            return
        scan_source(args.src, args.map)
    
    elif args.mode == "sync":
        if not args.dst:
            print("错误：同步模式需要指定 --dst 参数")
            return
        sync_target(args.dst, args.map, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
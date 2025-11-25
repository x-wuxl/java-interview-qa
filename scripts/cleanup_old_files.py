#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理脚本：删除旧的 collection 目录和临时文件
"""

import os
import shutil
from pathlib import Path

def cleanup():
    """清理废弃文件和目录"""
    
    print("=" * 60)
    print("开始清理废弃文件和目录")
    print("=" * 60)
    
    # 1. 删除旧的 collection 目录
    collection_dirs = [
        "_architecture",
        "_collections",
        "_concurrent",
        "_design-patterns",
        "_distributed-id",
        "_distributed-lock",
        "_distributed-theory",
        "_distributed-transaction",
        "_elasticsearch",
        "_java-basics",
        "_jvm",
        "_message-queue",
        "_microservices",
        "_mysql",
        "_netty",
        "_redis",
        "_rpc",
        "_sharding",
        "_spring",
        "_zookeeper"
    ]
    
    print("\n[1/4] 删除旧的 collection 目录...")
    removed_dirs = 0
    for dir_name in collection_dirs:
        dir_path = Path(dir_name)
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"  ✓ 删除: {dir_name}")
            removed_dirs += 1
    
    print(f"  共删除 {removed_dirs} 个 collection 目录")
    
    # 2. 删除临时和备份文件
    print("\n[2/4] 删除临时和备份文件...")
    temp_files = [
        "_config_simple.yml",
        "_config_backup.yml",
        "NAVIGATION_FIX.md",
        "DEPLOYMENT_GUIDE.md",
    ]
    
    removed_files = 0
    for file_name in temp_files:
        file_path = Path(file_name)
        if file_path.exists():
            file_path.unlink()
            print(f"  ✓ 删除: {file_name}")
            removed_files += 1
    
    print(f"  共删除 {removed_files} 个临时文件")
    
    # 3. 可选：删除 _posts 目录（保留作为备份，让用户手动决定）
    print("\n[3/4] _posts 目录处理...")
    if Path("_posts").exists():
        print("  ℹ️  保留 _posts 目录作为备份")
        print("  提示：确认新网站工作正常后，可手动删除：")
        print("      rm -rf _posts")
    
    # 4. 清理脚本目录中的旧脚本
    print("\n[4/4] 清理旧脚本...")
    old_scripts = [
        "scripts/migrate_to_collections.py",
        "scripts/cleanup_collections.py"
    ]
    
    removed_scripts = 0
    for script_name in old_scripts:
        script_path = Path(script_name)
        if script_path.exists():
            script_path.unlink()
            print(f"  ✓ 删除: {script_name}")
            removed_scripts += 1
    
    print(f"  共删除 {removed_scripts} 个旧脚本")
    
    print("\n" + "=" * 60)
    print("✓ 清理完成！")
    print("=" * 60)
    
    print("\n清理摘要:")
    print(f"  - 删除 collection 目录: {removed_dirs} 个")
    print(f"  - 删除临时文件: {removed_files} 个")
    print(f"  - 删除旧脚本: {removed_scripts} 个")
    print(f"  - 保留 _posts 目录: 作为备份")
    
    print("\n保留的重要目录:")
    print("  ✓ docs/ (新的内容目录)")
    print("  ✓ _data/ (数据文件)")
    print("  ✓ _includes/ (包含文件)")
    print("  ✓ _layouts/ (布局文件)")
    print("  ✓ _posts/ (原始备份)")
    print("  ✓ scripts/ (保留 migrate_to_docs.py)")
    
    print("\n下一步:")
    print("  1. 检查工作目录: git status")
    print("  2. 提交删除: git add -A")
    print("  3. 提交更改: git commit -m '清理旧文件和 collection 目录'")
    print("  4. 推送: git push origin main")


if __name__ == "__main__":
    cleanup()

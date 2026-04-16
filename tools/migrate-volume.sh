#!/bin/bash

# 嘿云枫！来，告诉我你要迁移哪个 Docker 命名卷？
read -p "请输入 Docker 命名卷的名称: " volume_name

if [ -z "$volume_name" ]; then
  echo "哎呀，卷名不能为空哦！"
  exit 1
fi

# 好的，那我们要把它存到 data 下的哪个文件夹里呢？
read -p "请输入目标文件夹名称 (将创建在 ./data/ 下): " dir_name

if [ -z "$dir_name" ]; then
  echo "文件夹名也不能为空呀！"
  exit 1
fi

target_path="./data/$dir_name"

echo "收到！准备把卷 '$volume_name' 里的东西搬运到 '$target_path' 去啦..."

# 创建目录
mkdir -p "$target_path"

# 执行 Docker 命令进行复制
docker run --rm \
  -v "$volume_name":/from \
  -v "$(pwd)/data/$dir_name":/to \
  alpine sh -c "ls -la /from && cp -a /from/. /to/"

echo "搞定啦！快去 '$target_path' 看看文件都在不在吧！"

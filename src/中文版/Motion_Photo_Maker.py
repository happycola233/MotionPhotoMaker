# 本程序使用exiftool：https://exiftool.org/

import argparse
import logging
import os
import shutil
import sys
import tempfile
from os.path import exists, basename, isdir, join
import subprocess

def source_path(relative_path):
    """
    获取资源文件的绝对路径，支持打包为exe后的情况。
    :param relative_path: 相对路径
    :return: 绝对路径
    """
    if getattr(sys, 'frozen', False):  # 如果程序是打包后的状态
        base_path = sys._MEIPASS  # 获取打包后的资源路径
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))  # 获取脚本文件的目录路径
    return os.path.join(base_path, relative_path)  # 拼接成完整路径并返回

def validate_directory(dir):
    """
    验证目录是否存在且是有效的目录。
    :param dir: 要验证的目录路径
    """
    if not exists(dir):  # 如果目录不存在
        logging.error("路径不存在: {}".format(dir))  # 记录错误日志
        sys.exit(1)  # 退出程序
    if not isdir(dir):  # 如果路径不是目录
        logging.error("路径不是目录: {}".format(dir))  # 记录错误日志
        sys.exit(1)  # 退出程序

def validate_media(photo_path, video_path):
    """
    检查提供的文件是否是有效的输入。目前只支持MP4/MOV和JPEG文件类型。
    目前它只检查文件扩展名，而不是通过文件签名字节实际检查文件格式。
    :param photo_path: 照片文件的路径
    :param video_path: 视频文件的路径
    :return: 如果照片和视频文件有效，则返回True，否则返回False
    """
    if not exists(photo_path):  # 如果照片文件不存在
        logging.error("照片不存在: {}".format(photo_path))  # 记录错误日志
        return False  # 返回False
    if not exists(video_path):  # 如果视频文件不存在
        logging.error("视频不存在: {}".format(video_path))  # 记录错误日志
        return False  # 返回False
    if not photo_path.lower().endswith(('.jpg', '.jpeg')):  # 如果照片文件不是JPEG格式
        logging.error("照片不是JPEG格式: {}".format(photo_path))  # 记录错误日志
        return False  # 返回False
    if not video_path.lower().endswith(('.mov', '.mp4')):  # 如果视频文件不是MOV或MP4格式
        logging.error("视频不是MOV或MP4格式: {}".format(video_path))  # 记录错误日志
        return False  # 返回False
    return True  # 返回True

def merge_files(photo_path, video_path, output_path):
    """
    将照片和视频文件合并在一起，通过将视频附加到照片的末尾。将输出写入指定的输出路径。
    :param photo_path: 照片的路径
    :param video_path: 视频的路径
    :param output_path: 输出目录的路径
    :return: 合并输出文件的文件名
    """
    logging.info("正在合并 {} 和 {}.".format(photo_path, video_path))  # 记录合并操作日志
    out_path = os.path.join(output_path, "{}".format(basename(photo_path)))  # 生成输出文件路径
    os.makedirs(os.path.dirname(out_path), exist_ok=True)  # 确保输出目录存在
    with open(out_path, "wb") as outfile, open(photo_path, "rb") as photo, open(video_path, "rb") as video:
        outfile.write(photo.read())  # 写入照片内容
        outfile.write(video.read())  # 写入视频内容
    logging.info("已合并照片和视频。")  # 记录合并完成日志
    return out_path  # 返回合并后的文件路径

def create_exiftool_config():
    """
    创建自定义ExifTool配置文件到临时目录。
    :return: 配置文件的路径
    """
    config_content = """
%Image::ExifTool::UserDefined = (
    'Image::ExifTool::XMP::Main' => {
        GCamera => {
            SubDirectory => {
                TagTable => 'Image::ExifTool::UserDefined::GCamera',
            },
        },
    },
);

%Image::ExifTool::UserDefined::GCamera = (
    GROUPS => { 0 => 'XMP', 1 => 'XMP-GCamera', 2 => 'Image' },
    NAMESPACE   => { 'GCamera' => 'http://ns.google.com/photos/1.0/camera/' },
    WRITABLE    => 'string',
    MicroVideo  => { Writable => 'integer' },
    MicroVideoVersion => { Writable => 'integer' },
    MicroVideoOffset => { Writable => 'integer' },
    MicroVideoPresentationTimestampUs => { Writable => 'integer' },
);

1;
"""
    temp_dir = tempfile.gettempdir()  # 获取临时目录
    config_path = os.path.join(temp_dir, "custom_exiftool.config")  # 生成配置文件路径
    with open(config_path, "w") as config_file:  # 打开配置文件
        config_file.write(config_content)  # 写入配置内容
    return config_path  # 返回配置文件路径

def add_xmp_metadata(merged_file, offset, config_path):
    """
    向合并的图像添加XMP元数据，指示文件中视频开始的字节偏移量。
    使用exiftool写入元数据。
    :param merged_file: 合并后的照片和视频文件的路径
    :param offset: 从文件末尾到视频开始部分的字节偏移量
    :param config_path: ExifTool配置文件的路径
    :return: None
    """
    exiftool_path = source_path('exiftool\\exiftool.exe')  # 获取exiftool的路径
    logging.info("ExifTool路径: {}".format(exiftool_path))
    logging.info("配置文件路径: {}".format(config_path))
    try:
        result = subprocess.run([
            exiftool_path,  # exiftool的路径
            '-config', config_path,  # 配置文件的路径
            '-XMP-GCamera:MicroVideo=1',  # 设置MicroVideo标志
            '-XMP-GCamera:MicroVideoVersion=1',  # 设置MicroVideo版本
            '-XMP-GCamera:MicroVideoOffset={}'.format(offset),  # 设置MicroVideo偏移量
            '-XMP-GCamera:MicroVideoPresentationTimestampUs=1500000',  # 设置展示时间戳（通常，Apple 会选择视频中的某个时间点作为展示照片的最佳时间点，这个时间点可能是视频开始后的 1.5 秒。）
            '-overwrite_original',  # 覆盖原文件，不生成备份
            merged_file  # 目标文件
        ], check=True, capture_output=True, text=True)  # 确保命令执行成功
        logging.info("ExifTool输出: {}".format(result.stdout))
        logging.info("已向文件添加XMP元数据。")  # 记录成功日志
    except subprocess.CalledProcessError as e:
        logging.error("添加XMP元数据失败: {}".format(e))  # 记录失败日志
        logging.error("ExifTool错误输出: {}".format(e.stderr))

def convert(photo_path, video_path, output_path):
    """
    执行转换过程，将文件合并为Google Motion Photo。
    :param photo_path: 要合并的照片路径
    :param video_path: 要合并的视频路径
    :param output_path: 输出目录的路径
    :return: 如果转换成功，则返回True，否则返回False
    """
    merged = merge_files(photo_path, video_path, output_path)  # 合并照片和视频文件
    photo_filesize = os.path.getsize(photo_path)  # 获取照片文件大小
    merged_filesize = os.path.getsize(merged)  # 获取合并后文件大小

    # XMP元数据中的'offset'字段应为从文件末尾到合并文件中视频部分开始的偏移量（以字节为单位）。
    # 合并大小 - 仅照片大小 = 偏移量。
    offset = merged_filesize - photo_filesize  # 计算偏移量
    config_path = create_exiftool_config()  # 创建ExifTool配置文件
    add_xmp_metadata(merged, offset, config_path)  # 添加XMP元数据
    os.remove(config_path)  # 删除临时配置文件

def matching_video(photo_path):
    """
    查找给定照片的匹配视频文件。
    :param photo_path: 照片文件的路径
    :return: 匹配的视频文件路径，如果未找到则为空字符串
    """
    base = os.path.splitext(photo_path)[0]  # 获取照片文件的基础名称（不含扩展名）
    logging.info("正在查找与之同名的视频: {}".format(base))  # 记录查找日志
    for ext in ['.mov', '.mp4', '.MOV', '.MP4']:  # 支持的扩展名列表
        video_path = base + ext  # 构建视频文件路径
        if os.path.exists(video_path):  # 如果视频文件存在
            return video_path  # 返回视频文件路径
    return ""  # 如果未找到匹配视频文件，则返回空字符串

def process_directory(file_dir):
    """
    递归遍历指定目录中的文件，生成可以转换的（照片，视频）路径元组列表。
    :param file_dir: 查找照片/视频以转换的目录
    :return: 包含匹配照片/视频对的列表
    """
    logging.info("正在处理目录: {}".format(file_dir))  # 记录处理目录日志
    
    file_pairs = []  # 初始化文件对列表
    for root, dirs, files in os.walk(file_dir):  # 递归遍历目录
        for file in files:  # 遍历文件
            file_fullpath = join(root, file)  # 获取文件的完整路径
            if file.lower().endswith(('.jpg', '.jpeg')) and matching_video(file_fullpath) != "":  # 如果文件是JPEG格式且有匹配的视频文件
                file_pairs.append((file_fullpath, matching_video(file_fullpath)))  # 添加到文件对列表

    logging.info("找到 {} 对文件。".format(len(file_pairs)))  # 记录找到的文件对数量
    logging.info("找到的图像/视频对的子集: {}".format(str(file_pairs[0:9])))  # 记录部分找到的文件对
    return file_pairs  # 返回文件对列表

def main(args):
    """
    主函数，解析命令行参数并执行相应操作。
    :param args: 命令行参数
    """
    logging_level = logging.INFO if args.verbose else logging.ERROR  # 根据参数设置日志级别
    logging.basicConfig(level=logging_level, stream=sys.stdout)  # 配置日志记录
    logging.info("启用详细日志记录")  # 记录启用详细日志记录

    outdir = args.output if args.output is not None else "output"  # 获取输出目录

    if args.dir is not None:  # 如果指定了目录参数
        validate_directory(args.dir)  # 验证目录有效性
        pairs = process_directory(args.dir)  # 处理目录，获取文件对
        processed_files = set()  # 初始化已处理文件集
        for pair in pairs:  # 遍历文件对
            if validate_media(pair[0], pair[1]):  # 验证文件对的有效性
                convert(pair[0], pair[1], outdir)  # 转换文件对
                processed_files.add(pair[0])  # 将处理过的文件添加到集合
                processed_files.add(pair[1])  # 将处理过的文件添加到集合

        if args.copyall:  # 如果指定了复制所有文件参数
            # 将剩余的文件复制到输出目录
            all_files = set(join(root, file) for root, dirs, files in os.walk(args.dir) for file in files)  # 获取所有文件集
            remaining_files = all_files - processed_files  # 计算剩余文件集

            logging.info("找到 {} 个剩余文件将被复制。".format(len(remaining_files)))  # 记录剩余文件数量

            if len(remaining_files) > 0:  # 如果有剩余文件
                # 确保目标目录存在
                os.makedirs(outdir, exist_ok=True)  # 创建输出目录
                
                for file in remaining_files:  # 遍历剩余文件
                    file_name = basename(file)  # 获取文件名
                    destination_path = join(outdir, file_name)  # 构建目标路径
                    shutil.copy2(file, destination_path)  # 复制文件到目标路径（保留原始文件的元数据）
    else:  # 如果未指定目录参数
        if args.photo is None and args.video is None:  # 如果未提供照片和视频参数
            logging.error("需要提供--dir或--photo和--video。")  # 记录错误日志
            sys.exit(1)  # 退出进程

        if bool(args.photo) ^ bool(args.video):  # 如果只提供了一个参数
            logging.error("必须同时提供--photo和--video。")  # 记录错误日志
            sys.exit(1)  # 退出进程

        if validate_media(args.photo, args.video):  # 验证文件的有效性
            convert(args.photo, args.video, outdir)  # 转换文件

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='将照片和视频合并为Google Motion Photo格式的照片')  # 创建命令行参数解析器
    parser.add_argument('-v', '--verbose', help='显示日志消息。', action='store_true')  # 添加详细日志参数
    parser.add_argument('-d', '--dir', type=str, help='处理包含照片/视频的目录。优先于--photo/--video')  # 添加目录参数
    parser.add_argument('-p', '--photo', type=str, help='要添加的JPEG照片的路径。')  # 添加照片参数
    parser.add_argument('-m', '--video', type=str, help='要添加的MOV视频的路径。')  # 添加视频参数
    parser.add_argument('-o', '--output', type=str, help='文件输出路径。')  # 添加输出目录参数
    parser.add_argument('-c', '--copyall', help='将未匹配的文件复制到目录中。', action='store_true')  # 添加复制所有文件参数

    main(parser.parse_args())  # 解析命令行参数并调用主函数

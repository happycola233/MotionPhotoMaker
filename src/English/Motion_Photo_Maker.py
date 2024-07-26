# This program uses exiftool: https://exiftool.org/

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
    Get the absolute path of the resource file, supporting the case when packaged as an exe.
    :param relative_path: Relative path
    :return: Absolute path
    """
    if getattr(sys, 'frozen', False):  # If the program is packaged
        base_path = sys._MEIPASS  # Get the resource path after packaging
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))  # Get the directory path of the script file
    return os.path.join(base_path, relative_path)  # Join into a complete path and return

def validate_directory(dir):
    """
    Verify if the directory exists and is valid.
    :param dir: Directory path to be validated
    """
    if not exists(dir):  # If the directory does not exist
        logging.error("Path does not exist: {}".format(dir))  # Log the error
        sys.exit(1)  # Exit the program
    if not isdir(dir):  # If the path is not a directory
        logging.error("Path is not a directory: {}".format(dir))  # Log the error
        sys.exit(1)  # Exit the program

def validate_media(photo_path, video_path):
    """
    Check if the provided files are valid inputs. Currently only supports MP4/MOV and JPEG file types.
    It currently checks file extensions only, not the actual file format through file signature bytes.
    :param photo_path: Path of the photo file
    :param video_path: Path of the video file
    :return: True if the photo and video files are valid, otherwise False
    """
    if not exists(photo_path):  # If the photo file does not exist
        logging.error("Photo does not exist: {}".format(photo_path))  # Log the error
        return False  # Return False
    if not exists(video_path):  # If the video file does not exist
        logging.error("Video does not exist: {}".format(video_path))  # Log the error
        return False  # Return False
    if not photo_path.lower().endswith(('.jpg', '.jpeg')):  # If the photo file is not in JPEG format
        logging.error("Photo is not in JPEG format: {}".format(photo_path))  # Log the error
        return False  # Return False
    if not video_path.lower().endswith(('.mov', '.mp4')):  # If the video file is not in MOV or MP4 format
        logging.error("Video is not in MOV or MP4 format: {}".format(video_path))  # Log the error
        return False  # Return False
    return True  # Return True

def merge_files(photo_path, video_path, output_path):
    """
    Merge the photo and video files together by appending the video to the end of the photo.
    Write the output to the specified output path.
    :param photo_path: Path of the photo
    :param video_path: Path of the video
    :param output_path: Path of the output directory
    :return: The filename of the merged output file
    """
    logging.info("Merging {} and {}.".format(photo_path, video_path))  # Log the merge operation
    out_path = os.path.join(output_path, "{}".format(basename(photo_path)))  # Generate the output file path
    os.makedirs(os.path.dirname(out_path), exist_ok=True)  # Ensure the output directory exists
    with open(out_path, "wb") as outfile, open(photo_path, "rb") as photo, open(video_path, "rb") as video:
        outfile.write(photo.read())  # Write the photo content
        outfile.write(video.read())  # Write the video content
    logging.info("Photo and video merged.")  # Log the completion of the merge
    return out_path  # Return the merged file path

def create_exiftool_config():
    """
    Create a custom ExifTool configuration file in a temporary directory.
    :return: Path of the configuration file
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
    temp_dir = tempfile.gettempdir()  # Get the temporary directory
    config_path = os.path.join(temp_dir, "custom_exiftool.config")  # Generate the configuration file path
    with open(config_path, "w") as config_file:  # Open the configuration file
        config_file.write(config_content)  # Write the configuration content
    return config_path  # Return the configuration file path

def add_xmp_metadata(merged_file, offset, config_path):
    """
    Add XMP metadata to the merged image, indicating the byte offset where the video starts in the file.
    Use exiftool to write the metadata.
    :param merged_file: Path of the merged photo and video file
    :param offset: Byte offset from the end of the file to the start of the video part
    :param config_path: Path of the ExifTool configuration file
    :return: None
    """
    exiftool_path = source_path('exiftool\\exiftool.exe')  # Get the path of exiftool
    logging.info("ExifTool path: {}".format(exiftool_path))
    logging.info("Config file path: {}".format(config_path))
    try:
        result = subprocess.run([
            exiftool_path,  # Path of exiftool
            '-config', config_path,  # Path of the configuration file
            '-XMP-GCamera:MicroVideo=1',  # Set the MicroVideo flag
            '-XMP-GCamera:MicroVideoVersion=1',  # Set the MicroVideo version
            '-XMP-GCamera:MicroVideoOffset={}'.format(offset),  # Set the MicroVideo offset
            '-XMP-GCamera:MicroVideoPresentationTimestampUs=1500000',  # Set the presentation timestamp (Usually, Apple selects a point in the video as the best time point to present the photo, this point may be 1.5 seconds after the video starts.)
            '-overwrite_original',  # Overwrite the original file, do not generate a backup
            merged_file  # Target file
        ], check=True, capture_output=True, text=True)  # Ensure the command runs successfully
        logging.info("ExifTool output: {}".format(result.stdout))
        logging.info("XMP metadata added to the file.")  # Log the success
    except subprocess.CalledProcessError as e:
        logging.error("Failed to add XMP metadata: {}".format(e))  # Log the failure
        logging.error("ExifTool error output: {}".format(e.stderr))

def convert(photo_path, video_path, output_path):
    """
    Perform the conversion process to merge the files into a Google Motion Photo.
    :param photo_path: Path of the photo to be merged
    :param video_path: Path of the video to be merged
    :param output_path: Path of the output directory
    :return: True if the conversion is successful, otherwise False
    """
    merged = merge_files(photo_path, video_path, output_path)  # Merge the photo and video files
    photo_filesize = os.path.getsize(photo_path)  # Get the photo file size
    merged_filesize = os.path.getsize(merged)  # Get the merged file size

    # The 'offset' field in XMP metadata should be the byte offset from the end of the file to the start of the video part in the merged file.
    # Merged size - photo size = offset.
    offset = merged_filesize - photo_filesize  # Calculate the offset
    config_path = create_exiftool_config()  # Create the ExifTool configuration file
    add_xmp_metadata(merged, offset, config_path)  # Add XMP metadata
    os.remove(config_path)  # Delete the temporary configuration file

def matching_video(photo_path):
    """
    Find the matching video file for the given photo.
    :param photo_path: Path of the photo file
    :return: Path of the matching video file, or an empty string if not found
    """
    base = os.path.splitext(photo_path)[0]  # Get the base name of the photo file (without extension)
    logging.info("Looking for a video with the same name: {}".format(base))  # Log the search
    for ext in ['.mov', '.mp4', '.MOV', '.MP4']:  # List of supported extensions
        video_path = base + ext  # Construct the video file path
        if os.path.exists(video_path):  # If the video file exists
            return video_path  # Return the video file path
    return ""  # If no matching video file is found, return an empty string

def process_directory(file_dir):
    """
    Recursively traverse the files in the specified directory, generating a list of tuples of (photo, video) paths that can be converted.
    :param file_dir: Directory to search for photos/videos to convert
    :return: List of matching photo/video pairs
    """
    logging.info("Processing directory: {}".format(file_dir))  # Log the directory processing
    
    file_pairs = []  # Initialize the list of file pairs
    for root, dirs, files in os.walk(file_dir):  # Recursively traverse the directory
        for file in files:  # Traverse the files
            file_fullpath = join(root, file)  # Get the full path of the file
            if file.lower().endswith(('.jpg', '.jpeg')) and matching_video(file_fullpath) != "":  # If the file is in JPEG format and has a matching video file
                file_pairs.append((file_fullpath, matching_video(file_fullpath)))  # Add to the list of file pairs

    logging.info("Found {} pairs of files.".format(len(file_pairs)))  # Log the number of file pairs found
    logging.info("Subset of found image/video pairs: {}".format(str(file_pairs[0:9])))  # Log a subset of the found file pairs
    return file_pairs  # Return the list of file pairs

def main(args):
    """
    Main function, parses command line arguments and performs corresponding operations.
    :param args: Command line arguments
    """
    logging_level = logging.INFO if args.verbose else logging.ERROR  # Set the logging level based on the argument
    logging.basicConfig(level=logging_level, stream=sys.stdout)  # Configure logging
    logging.info("Detailed logging enabled")  # Log enabling detailed logging

    outdir = args.output if args.output is not None else "output"  # Get the output directory

    if args.dir is not None:  # If the directory argument is specified
        validate_directory(args.dir)  # Validate the directory
        pairs = process_directory(args.dir)  # Process the directory to get the file pairs
        processed_files = set()  # Initialize the set of processed files
        for pair in pairs:  # Traverse the file pairs
            if validate_media(pair[0], pair[1]):  # Validate the file pair
                convert(pair[0], pair[1], outdir)  # Convert the file pair
                processed_files.add(pair[0])  # Add the processed file to the set
                processed_files.add(pair[1])  # Add the processed file to the set

        if args.copyall:  # If the copy all files argument is specified
            # Copy the remaining files to the output directory
            all_files = set(join(root, file) for root, dirs, files in os.walk(args.dir) for file in files)  # Get the set of all files
            remaining_files = all_files - processed_files  # Calculate the set of remaining files

            logging.info("Found {} remaining files to be copied.".format(len(remaining_files)))  # Log the number of remaining files

            if len(remaining_files) > 0:  # If there are remaining files
                # Ensure the target directory exists
                os.makedirs(outdir, exist_ok=True)  # Create the output directory
                
                for file in remaining_files:  # Traverse the remaining files
                    file_name = basename(file)  # Get the file name
                    destination_path = join(outdir, file_name)  # Construct the target path
                    shutil.copy2(file, destination_path)  # Copy the file to the target path (retain the original file's metadata)
    else:  # If the directory argument is not specified
        if args.photo is None and args.video is None:  # If photo and video arguments are not provided
            logging.error("Need to provide --dir or both --photo and --video.")  # Log the error
            sys.exit(1)  # Exit the process

        if bool(args.photo) ^ bool(args.video):  # If only one argument is provided
            logging.error("Must provide both --photo and --video.")  # Log the error
            sys.exit(1)  # Exit the process

        if validate_media(args.photo, args.video):  # Validate the files
            convert(args.photo, args.video, outdir)  # Convert the files

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Merge photos and videos into Google Motion Photo format')  # Create the command line argument parser
    parser.add_argument('-v', '--verbose', help='Display log messages.', action='store_true')  # Add verbose logging argument
    parser.add_argument('-d', '--dir', type=str, help='Directory containing photos/videos to process. Takes precedence over --photo/--video')  # Add directory argument
    parser.add_argument('-p', '--photo', type=str, help='Path of the JPEG photo to be added.')  # Add photo argument
    parser.add_argument('-m', '--video', type=str, help='Path of the MOV video to be added.')  # Add video argument
    parser.add_argument('-o', '--output', type=str, help='Path of the output directory.')  # Add output directory argument
    parser.add_argument('-c', '--copyall', help='Copy unmatched files to the directory.', action='store_true')  # Add copy all files argument

    main(parser.parse_args())  # Parse the command line arguments and call the main function

import base64
import os
import re
import json
from datetime import datetime
import boto3
from botocore.exceptions import ClientError
import io


def encode_image(image_path):

        return base64.b64encode(image_path.read()).decode("utf-8")


DEFAULT_DIR_PATH = "./"
files_path = os.path.join(DEFAULT_DIR_PATH, "files")

def save_files(files_list):
    if not os.path.exists(files_path):
        os.system(f"mkdir {files_path}")
    for file in files_list:
        # file.name = file.name.replace(" ","_")
        save_path = f"{files_path}/{file.name}"
        pattern = re.compile(r".\.(jpg|jpeg|png)$", re.IGNORECASE)
        match = re.search(pattern, save_path)
        if match:
            with open(save_path, mode='wb') as w:
                w.write(file.getvalue())
        else:
            im = Image.open(file)
            im.save(save_path)
    return True

def find_matching_json(response_content, bucket_name, jsonl_file_name, s3):
    matching_jsons = []
    latest_matching_json = None
    latest_date = None

    try:
        # Get the object from S3
        s3_object = s3.get_object(Bucket=bucket_name, Key="metadata/"+jsonl_file_name)
        # Read the content of the file
        content = s3_object['Body'].read().decode('utf-8')

        # Process each line of the file
        for line in io.StringIO(content):
            json_data = json.loads(line.strip())
            
            # Check if seller_name and seller_email match
            if (json_data['seller_name'] == response_content['seller_name'] and
                json_data['seller_email'] == response_content['seller_email']):
                matching_jsons.append(json_data)
    
        # If we have matches, find the one with the latest date_of_issue
        if matching_jsons:
            for json_data in matching_jsons:
                date_str = json_data['date_of_issue']
                try:
                    current_date = datetime.strptime(date_str, '%Y-%m-%d')  # Adjust format if needed
                    if latest_date is None or current_date > latest_date:
                        latest_date = current_date
                        latest_matching_json = json_data
                except ValueError:
                    print(f"Invalid date format in JSON: {date_str}")
    
    except ClientError as e:
        print(f"Error accessing S3 file: {e}")
    
    return latest_matching_json

def get_image_from_s3(bucket_name,IMAGES_FOLDER ,file_name, s3):
    try:
        # Construct the full path in S3
        s3_path = f"{IMAGES_FOLDER}/{file_name}"
        
        # Get the object from S3
        response = s3.get_object(Bucket=bucket_name, Key=s3_path)
        
        # Read the content of the file
        image_content = response['Body'].read()
        
        # Encode the image to base64 and decode to get a UTF-8 string
        image_string = base64.b64encode(image_content).decode("utf-8")
        
        return image_string
    except ClientError as e:
        print(f"Error accessing S3 image: {e}")
        return None








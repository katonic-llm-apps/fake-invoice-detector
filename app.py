import streamlit as st 
from streamlit_option_menu import option_menu
import requests
import numpy as np
from io import BytesIO
import os
import openai
from PIL import Image
import csv
import json
import pandas as pd
import base64
import re
import sys
import boto3
from botocore.exceptions import ClientError
import io
from datetime import datetime
from IPython.display import Image, display, Audio, Markdown
from langchain.chat_models import ChatOpenAI
from utils import(encode_image,save_files,find_matching_json,get_image_from_s3)

st.set_page_config(
    page_title='Vendor Invoice Check ',
    layout="centered",
    )

os.environ["AWS_ACCESS_KEY"]=os.getenv("AWS_ACCESS_KEY")
os.environ["AWS_SECRET_KEY"]=os.getenv("AWS_SECRET_KEY")
REGION=os.getenv("REGION")
S3_BUCKET_NAME= os.getenv("S3_BUCKET_NAME")
DATABASE_FILENAME = os.getenv("DATABASE_FILENAME")
IMAGES_FOLDER = os.getenv("IMAGES_FOLDER")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

AWS_S3_CREDS = {
           "aws_access_key_id":os.environ["AWS_ACCESS_KEY"],
           "aws_secret_access_key":os.environ["AWS_SECRET_KEY"],
            "region_name": REGION
           }

s3 = boto3.client('s3',**AWS_S3_CREDS)

with st.sidebar:
    # st.image('image/logo.png')
    selected = option_menu(
        menu_title="Main Menu",
        options=["About the App", "Check Invoice"])

if selected=="Check Invoice":
    
    # st.image("Deloitte.png",width=175)
    st.markdown("""
        <style>
            .top-bar {
                background-color: #FFFFFF;
                color: black;
                padding: 10px;
                font-size: 32px;
                text-align: left;
                border-radius: 10px 10px 5px 5px;
                position: relative;
                margin: 0px;
                font-weight: bold;
                margin-left: -12.5px;
                margin-right: 0px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
              
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<h1> Vendor Invoice Check</h1>', unsafe_allow_html=True)

    with open("style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    MODEL = "gpt-4o"



    
    llm_model = ChatOpenAI(model="gpt-4o",openai_api_key= OPENAI_API_KEY,temperature=0.0)
    
    uploaded_file = st.file_uploader("Please provide an Image", type=["jpeg", "png"], accept_multiple_files=False,label_visibility='visible')

    if uploaded_file:
        
        DEFAULT_DIR_PATH = "./"
        files_path = os.path.join(DEFAULT_DIR_PATH, "files")

        col1, col2, col3 = st.columns([1.75, 4, 1])
        with col1:
            st.write("")
        with col2:
            
            st.image(uploaded_file,caption=f"Uploaded Image: {uploaded_file.name}",width=300)
            
        with col3:
            st.write("")

        base64_image = encode_image(uploaded_file)

        folder_name = '/home/katonic/uploaded_files'    
        os.makedirs(folder_name, exist_ok=True)     
        image_path = os.path.join(folder_name, uploaded_file.name)

        if st.button("Start Processing",use_container_width=True):
            with st.spinner("Generating the response.. takes some time⏳"):

                messages=[
                        {"role": "system", "content": "You are a helpful assistant that responds in Markdown. Help me with my work!"},
                        {"role": "user", "content": [
                            {"type": "text", "text": """ You need to create a json of the input image which has the details about the metadata of the image.
                                                            Date of Invoice Format: YYYY-MM-DD
                                                            The metadata json will look like this :
                                                            {   
                                                                "seller_name":"",
                                                                "seller_address": "",
                                                                "seller_contact": "",
                                                                "seller_email": "",
                                                                "invoice_number": "",
                                                                "date_of_issue": "",
                                                                "buyer_name": "",
                                                                "total_price": "" 
                                                            }
                                                            
                                                            IMPORTANT: JUST RETURN THE JSON AND NOTHING ELSE
                            """},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                        ]}
                    ]
                response_content = llm_model.invoke(messages).content

                if '```' in response_content:
                    response_content = response_content.split('```')[1].replace('json', "").replace('JSON',"")
                    
                response_content = json.loads(response_content)

    
                matching_json = find_matching_json(response_content, S3_BUCKET_NAME, DATABASE_FILENAME,s3)

                if matching_json is None:
                    st.info("No matching invoice found in database.", icon="ℹ️")
                    sys.exit(1)


                matched_file_path = matching_json["file_path"]


                if matched_file_path:
                    # st.success(f"Similar Invoice found! {matched_file_path}")
                    
                    def get_image_response(base64_image, matched_file_path):

                        matched_image_string = get_image_from_s3(S3_BUCKET_NAME,IMAGES_FOLDER ,matched_file_path, s3)


                        messages = [
                            {"role": "system", "content": "You are a helpful assistant that compares given invoice to multiple records in database ."},
                            {"role": "user", "content": [
                                {"type": "text", "text": """You are reviewing an invoice and comparing it to database . Based on the cases below, follow the inspection criteria and note your findings in the justification section.

                                                CASE 1: Duplicate Invoices
                                                    Inspection Criteria:
                                                        Check if the invoice number matches any existing records in the database.
                                                        If yes,Check if the invoice amount is consistent with previous entries for the same invoice number.
                                                        Check if the same invoice has been submitted under different buyer names.
                                                    Inspection Check:
                                                        Is the given invoice number found identical with database records?
                                                        Is the given invoice amount is same as any record in database?
                                                        Has the same invoice been submitted by different buyers?
                                                    Remark:
                                                        Identify duplicate invoices viz. same invoice number, same amount raised every month, same invoice submitted by multiple employees.If checks suggest duplication, then mark it as YES.

                                                CASE 2: Invoice Format Changes
                                                    Inspection Criteria:
                                                        Check if the given invoice letterhead is different from the database invoices of the same vendor.
                                                        Check if the given font style is different from the database invoices of the same vendor.
                                                        Check if the given invoice design is different from the database invoices of the same vendor.
                                                    Inspection Check:
                                                        Is the letterhead different for the invoice generated by same vendor?
                                                        Is the Font style different for the invoice generated by same vendor?
                                                        Is the design different for the invoice generated by same vendor?
                                                    Remark:
                                                        Identify instances wherein format of the invoice of the same vendor has been changed compared to previous versions (change in letter head, change in font style, change in design). If yes, mark it as YES

                                                CASE 3: Changes in Sign & Stamp
                                                    Inspection Criteria:
                                                        Check if the sign and stamp exits in given invoice.
                                                        If yes, Check if the same seller has a different signature or stamp in its database invoices.
                                                        Note: If the sign is missing in any of the records then mark it as NA because there is no comparison.
                                                    Inspection Check:
                                                        Is the signature same in the invoice generated by same vendor in the database?
                                                        Is the stamp same in the invoice generated by same vendor in the database?
                                                        Is there any Style changes in sign or stamp of same vendor in the database?
                                                    Remark:
                                                        if sign or stamp is present in given image and database then check If any changes are found in the signature or stamp by the same vendor to the database, mention the differences found in the style compared to the stored records.If crteria fulfils ,mark it as YES, otherwise mark it as No

                                                CASE 4: Pricing Discrepancies
                                                    Inspection Criteria:
                                                        Check if both the invoices have same product in the invoice given and the database.
                                                        If any same product does not exist in database, then consider it a No.
                                                        If same product is mentioned,Compare the rate charged for the product or service with previous invoices from the same vendor.
                                                    Inspection Check:
                                                        Is the rate same for same product or services given by the same vendor?    
                                                    Remark:
                                                        If any instances exist wherein different rate has been charged for same type of services / products in different invoices of the same vendor, mark it as YES.

                                                For each case, ensure the findings are thoroughly compared against the database, and report the findings based on the criteria above. Provide an overall summary at the end.
                                                Each Check should be answered by either "✅" or "❌", with a justification provided in the Justification column. If the answer is Not Applicable, consider it No.
                                                
                                                Note for Framing Response:
                                                    - THE JUSTIFICATION SHOULD BE FRAMED AS THOUGH THEY ARE BEING COMPARED TO THE DATABASE, NOT AN INDIVIDUAL IMAGE.

                                                There should be justification for each and every Inspection check.
                                                

                                                Note for JSON format:
                                                    - The last object (which contains the Overall Summary) should be part of the array in the main object at the end.

                                                You must return the response in proper JSON format with the following columns: Inspection Check, Result , Justification, and Overall Summary.
                                                
                                                IMPORTANT: THE RESPONSE SHOULD NOT BE RANDOM, AND YOU MUST STRICTLY READ THROUGH THE CRITERIA AND TAKE DECISION.
                                                """},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{matched_image_string}"}}
                            ]}
                        ]

                        llm_response = llm_model.invoke(messages).content

                        if '```' in llm_response:
                            llm_response = llm_response.split('```')[1].replace('json', "").replace('JSON',"")

                        return llm_response
                    

                    response = get_image_response(base64_image, matched_file_path)
                    response = json.loads(response)

                    sections = {
                        "Duplicate Invoices": [0, 1, 2],
                        "Edited Invoices": [3, 4, 5],
                        "Changes in Sign & Stamp": [6, 7, 8],
                        "Pricing Discrepancies": [9],
                        "Overall Summary": [10]
                    }

                    # Prepare the formatted data
                    formatted_data = []

                    for section, indices in sections.items():
                        if section != "Overall Summary":
                            # Add section name as a row
                            formatted_data.append([section, '', ''])
                        
                        # For each index in the section, get the corresponding data
                        for idx in indices:
                            entry = response[idx]
                            if 'Inspection Check' in entry:
                                # Add inspection check, result, and justification under the section
                                formatted_data.append([
                                    entry['Inspection Check'],
                                    entry['Result'],
                                    entry['Justification']
                                ])
                            elif 'Overall Summary' in entry:
                                formatted_data.append(['', '', ''])
                                formatted_data.append(['Overall Summary', '', entry['Overall Summary']])

                    # Create DataFrame with the required columns
                    df = pd.DataFrame(formatted_data, columns=['Inspection Check', 'Result', 'Justification'])

                    st.data_editor(
                        df,
                        column_config={
                            "Inspection Check": st.column_config.Column(
                                "Inspection Check",
                                width="large",
                                required=True,
                            ),
                            "Result": st.column_config.Column(
                                "Result",
                                width="medium",
                                required=True,
                            )
                        },
                        hide_index=True,
                        disabled=True,
                        height=600
                    )

if selected=="About the App":
    st.title("Welcome to Invoice Management Application!")

    st.write(
        "In today's fast-paced business world, keeping track of invoices can be a daunting task. "
        "This app simplifies this process, empowering you to manage your invoices with ease and confidence."
    )

    st.subheader("Key Features:")
    
    features = {
        "🔍 Smart Duplicate Detection": (
            "Say goodbye to confusion and errors! This app intelligently scans your invoices to identify any duplicates, "
            "helping you maintain accurate records."
        ),
        "📝 Comprehensive Editing Insights": (
            "Have you ever received an edited invoice and wondered about the changes? "
            "This app highlights all modifications, allowing you to stay informed and make well-informed decisions."
        ),
        "💰 Pricing Discrepancy Alerts": (
            "Spot pricing inconsistencies before they become a problem. "
            "This app monitors your invoices for any unexpected pricing changes, ensuring you’re always in control of your finances."
        ),
        "✍️ Sign & Stamp Verification": (
            "Verify any alterations in signatures or stamps to maintain the integrity of your documents. "
            "This app provides a clear overview of these changes, keeping you one step ahead."
        ),
        "📊 Detailed Reporting": (
            "Gain valuable insights into your invoice management with structured summaries. "
            "This app categorizes findings into easy-to-read sections, giving you a comprehensive view of your invoicing landscape."
        ),
    }

    for feature, description in features.items():
        st.markdown(f"**{feature}**")
        st.write(description)
        st.write("")  # Add an empty line for spacing
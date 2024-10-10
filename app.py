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
import boto3
from botocore.exceptions import ClientError
import io
from datetime import datetime
from IPython.display import Image, display, Audio, Markdown
from langchain.chat_models import ChatOpenAI
from utils import(encode_image,save_files,find_matching_json,get_image_from_s3)

st.set_page_config(
    page_title='Fake Invoice Detection ',
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


def main():
    
    st.image("Deloitte.png",width=175)
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

    st.markdown('<h1> Fake Invoice Detection</h1>', unsafe_allow_html=True)

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
                    st.success(f"Similar Invoice found! {matched_file_path}")
                    
                    def get_image_response(base64_image, matched_file_path):

                        matched_image_string = get_image_from_s3(S3_BUCKET_NAME,IMAGES_FOLDER ,matched_file_path, s3)


                        messages = [
                            {
                                "role": "system", 
                                "content": "You are a helpful assistant that compares given invoice to the database."
                            },
                            {
                                "role": "user", 
                                "content": [
                                    {
                                        "type": "text", 
                                        "text": """
                                        You are reviewing an invoice and comparing it to historical records or data stored in a database. Based on the cases below, follow the inspection criteria and note your findings in the remarks section.

                                        CASE 1: Duplicate Invoices
                                            Inspection Criteria:
                                                Check if the invoice number matches any existing records.
                                                Check if the invoice amount is consistent with previous entries for the same invoice.
                                                Check if the same invoice has been submitted under different employee names.
                                            Inspection Check:
                                                Are the invoice number, amount, and submission details (such as employee information) consistent with previous records in the database?
                                            Remark:
                                                Provide justification based on the database comparison, highlighting if the invoice is a duplicate or not wrt to the database.

                                        CASE 2: Invoice Format Changes
                                            Inspection Criteria:
                                                Check if the given invoice letterhead is different from the database invoices.
                                                Check if the given font style letterhead is different from the database invoices.
                                                Check if the given invoice design is different from the database invoices.
                                            Inspection Check:
                                                Has the invoice letterhead,font style or invoice design of the invoice changed compared to previous submissions by the same vendor?
                                            Remark:
                                                Mention any noticeable changes in the invoice design, font, or layout when compared to historical records.

                                        CASE 3: Changes in Sign & Stamp
                                            Inspection Criteria:
                                                Check is the sign and stamp exits in both the invoice.
                                                If yes, Check if the signature or stamp differs from historical records from the same Seller.
                                                If yes, Verify if the same seller has unauthorized alterations in sign or stamp 
                                            Inspection Check:
                                                If the stamp or sign exist in both the invoice, Has the signature or stamp changed compared to previous database invoices?
                                            Remark:
                                                Provide details on any changes in the signature or stamp of the same seller, mentioning if it appears unauthorized based on database records.If Sign or stamp do not exist in both or exist in either of images of the invoice,then mark it as No.

                                        CASE 4: Pricing Discrepancies
                                            Inspection Criteria:
                                                Check if both the invoices have same product in the invoice.
                                                If same product is mentioned,Compare the rate charged for the product or service with previous invoices from the same vendor.
                                                compare if the service/product description is consistent with previous records.
                                            Inspection Check:
                                                Is the pricing different for the same service or product across invoices provided by the same vendor?
                                            Remark:
                                                Mention discrepancies in product/service pricing for the same product provided by the same vendor.If same product does not exist, then mark it as No.

                                        Provide an overall summary at the end of all checks.Overall summary should mention the case name in which it lies with proper justification.
                                        Each Inspection Criteria should be answered Yes or No, with a justification provided in the Inspection Remarks section.
                                        If the answer is Not Applicable, consider it No.

                                        IMPORTANT: The Inspection remarks should be framed as though they are being compared to the database, not an individual image.
                                        
                                        Note for JSON format:
                                            - The last object should contain the Overall Summary and be part of the array or a separate key in the main object.
                                            
                                        Return the response in proper JSON format with the following columns: Inspection Criteria, Inspection Check ,Result(Yes/No), Inspection Remarks (justification), and an Overall Summary.
                                        IMPORTANT: THE RESPONSE SHOULD NOT BE RANDOM, AND YOU MUST STRICTLY READ THROUGH THE CRITERIA AND TAKE DECISION.
                                        """
                                    },
                                    {
                                        "type": "image_url", 
                                        "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                                    },
                                    {
                                        "type": "image_url", 
                                        "image_url": {"url": f"data:image/png;base64,{matched_image_string}"}
                                    }
                                ]
                            }
                        ]

                        llm_response = llm_model.invoke(messages).content

                        if '```' in llm_response:
                            llm_response = llm_response.split('```')[1].replace('json', "").replace('JSON',"")

                        return llm_response
                    

                    response = get_image_response(base64_image, matched_file_path)
                    response = json.loads(response)

                inspection_items = [item for item in response if 'Inspection Criteria' in item]
                overall_summary = next((item['Overall Summary'] for item in response if 'Overall Summary' in item), None)

                df = pd.DataFrame(inspection_items)

                if overall_summary:
                    summary_row = pd.DataFrame({
                        'Inspection Criteria': ['Overall Summary'],
                        'Inspection Check': [''],
                        'Result': [''],
                        'Inspection Remarks': [overall_summary]
                    })
                    df = pd.concat([df, summary_row], ignore_index=True)

                df = pd.DataFrame(df)
                st.dataframe(df,hide_index=True,height=None)
      

if __name__ == "__main__":
    main()

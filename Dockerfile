FROM quay.io/katonic/katonic-base-images:py39-base-conda4.9.2

COPY .streamlit .streamlit
COPY app.py .
COPY utils.py .
COPY requirements.txt .
COPY style.css .
COPY Deloitte.png .
RUN pip install -r requirements.txt

CMD streamlit run app.py --server.port=8050 --server.address=0.0.0.0 --logger.level error
FROM python:3.10-slim

# Instale pacotes de localidade e o locale-gen
RUN apt-get update && apt-get install -y locales

# Gera a localidade 'pt_BR.UTF-8'
RUN sed -i '/pt_BR.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen

# Definir as variáveis de ambiente para o locale
ENV LANG pt_BR.UTF-8  
ENV LANGUAGE pt_BR:pt  
ENV LC_ALL pt_BR.UTF-8  

WORKDIR /app

COPY requirements.txt .

# Instale as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Copie todo o conteúdo do diretório local para o contêiner
COPY . .

EXPOSE 8091

CMD ["streamlit", "run", "Dias_Livres_por_Voo.py", "--server.port=8091"]

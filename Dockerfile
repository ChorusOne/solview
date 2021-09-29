FROM python:3.9-alpine3.14

RUN apk update --no-cache

ENV SOLVIEW_NODE_ADDRESS=https://api.mainnet-beta.solana.com

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt && rm requirements.txt

COPY solview.py /usr/local/bin/solview

RUN chmod +x /usr/local/bin/solview

RUN adduser solview -D -S -H

USER solview

CMD /usr/local/bin/solview



FROM node:20-bookworm-slim

WORKDIR /app

# Python is needed because this panel starts bot.py from Node.
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

COPY package*.json ./
RUN npm ci --omit=dev

COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

ENV NODE_ENV=production
EXPOSE 3000

CMD ["npm", "start"]

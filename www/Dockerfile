FROM node:16-alpine

WORKDIR /home/node/src
COPY package*.json .
RUN npm clean-install

EXPOSE 3000

COPY . .

CMD ["npm", "start"]
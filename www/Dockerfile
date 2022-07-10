FROM node:16-alpine

USER node

WORKDIR /home/node/src
COPY package*.json .
RUN npm clean-install

EXPOSE 3000

COPY . .

CMD ["npm", "start"]
FROM node:20-alpine AS base

WORKDIR /app

# Build the shared package
COPY shared/ ./shared/
WORKDIR /app/shared
RUN npm install && npm run build

# Install and build frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ ./

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

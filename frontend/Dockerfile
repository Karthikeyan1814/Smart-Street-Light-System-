FROM node:20-alpine

WORKDIR /app

# Copy dependency specifications first for layer caching
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm install

# Copy application source code
COPY . .

# Expose Vite development server port
EXPOSE 5173

# Start Vite server with host exposed
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]


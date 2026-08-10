FROM mirror.gcr.io/library/node:20-alpine
WORKDIR /app
COPY package.json ./
RUN npm install --no-audit --no-fund

FROM mirror.gcr.io/library/node:20-alpine
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-slim
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=build /app/package.json ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/.next ./.next
COPY --from=build /app/public ./public
EXPOSE 3005
CMD ["npm", "run", "start"]

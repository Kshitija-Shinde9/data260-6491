# Use Nginx as the base image
FROM nginx:alpine

# Remove default Nginx HTML files
RUN rm -rf /usr/share/nginx/html/*

# Copy all frontend files (HTML, CSS, JS) into the Nginx web root
COPY . /usr/share/nginx/html/

# Change nginx's internal listening port from 80 to 8191 (our PORT_BASE)
RUN sed -i 's/listen\s*80;/listen 8191;/' /etc/nginx/conf.d/default.conf

# Expose port 8191 (matches PORT_BASE)
EXPOSE 8191

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]


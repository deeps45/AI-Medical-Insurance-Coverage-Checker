# 🚀 Deployment Guide for Render

This guide will walk you through deploying your AI Medical Insurance Coverage Checker to Render.

## 📋 Prerequisites

1. **GitHub Account**: Your code must be in a GitHub repository
2. **Render Account**: Sign up at [render.com](https://render.com)
3. **API Keys**: 
   - OpenAI API key from [platform.openai.com](https://platform.openai.com/)
   - Pinecone API key from [pinecone.io](https://pinecone.io/)

## 🎯 Option 1: Blueprint Deployment (Recommended)

### Step 1: Prepare Your Repository

1. **Push your code to GitHub**:
   ```bash
   git add .
   git commit -m "Prepare for Render deployment"
   git push origin main
   ```

2. **Ensure these files are in your repository**:
   - `render.yaml` ✅
   - `Dockerfile` ✅
   - `backend/` directory ✅
   - `frontend/` directory ✅

### Step 2: Deploy on Render

1. **Go to [render.com](https://render.com)** and sign in
2. **Click "New +"** and select **"Blueprint"**
3. **Connect your GitHub account** if not already connected
4. **Select your repository**: `ai-medical-insurance-coverage-checker`
5. **Render will automatically detect** the `render.yaml` file
6. **Click "Connect"** to proceed

### Step 3: Configure Environment Variables

1. **Add your API keys** in the Environment section:
   - `OPENAI_API_KEY`: Your OpenAI API key (starts with `sk-`)
   - `PINECONE_API_KEY`: Your Pinecone API key (starts with `pcsk_`)

2. **Click "Apply"** to save the configuration

### Step 4: Deploy!

1. **Click "Create New Resources"**
2. **Wait for deployment** (usually 5-10 minutes)
3. **Your app will be available at**: `https://ai-medical-insurance-checker.onrender.com`

## 🎯 Option 2: Manual Deployment

### Step 1: Create Web Service

1. **Click "New +"** → **"Web Service"**
2. **Connect your GitHub repository**
3. **Configure the service**:
   - **Name**: `ai-medical-insurance-checker`
   - **Environment**: `Docker`
   - **Branch**: `main`
   - **Build Command**: `docker build -t ai-medical-insurance-checker .`
   - **Start Command**: `docker run -p 10000:8501 ai-medical-insurance-checker`

### Step 2: Create PostgreSQL Database

1. **Go back to dashboard** and click **"New +"**
2. **Select "PostgreSQL"**
3. **Configure**:
   - **Name**: `ai-medical-insurance-db`
   - **Plan**: `Starter` (free tier)
   - **Region**: Choose closest to you

### Step 3: Link Database to Web Service

1. **Go back to your web service**
2. **Click "Environment"** tab
3. **Add environment variable**:
   - **Key**: `DATABASE_URL`
   - **Value**: Copy from PostgreSQL service connection string

### Step 4: Add Other Environment Variables

Add these environment variables:

```
OPENAI_API_KEY=sk-your-openai-api-key
PINECONE_API_KEY=pcsk-your-pinecone-api-key
PINECONE_ENVIRONMENT=us-east-1-aws
PINECONE_INDEX_NAME=docsage-lite
BASE_URL=http://localhost:8000
RENDER=true
TESSERACT_CMD=/usr/bin/tesseract
PORT=8501
```

## 🔧 Post-Deployment Configuration

### 1. Test Your Application

1. **Visit your app URL**: `https://your-app-name.onrender.com`
2. **Upload a test PDF** to verify functionality
3. **Ask a test question** to ensure AI is working

### 2. Monitor Logs

1. **Go to your web service** on Render
2. **Click "Logs"** tab
3. **Check for any errors** or warnings

### 3. Set Up Custom Domain (Optional)

1. **Go to your web service** → **"Settings"** tab
2. **Click "Custom Domains"**
3. **Add your domain** and configure DNS

## 🚨 Troubleshooting

### Common Issues

1. **Build Fails**
   - Check Dockerfile syntax
   - Ensure all files are committed to GitHub
   - Check Render logs for specific errors

2. **App Won't Start**
   - Verify environment variables are set correctly
   - Check if database is accessible
   - Review startup logs

3. **Database Connection Issues**
   - Ensure `DATABASE_URL` is correct
   - Check if database service is running
   - Verify network connectivity

4. **API Key Issues**
   - Double-check API keys are correct
   - Ensure keys have proper permissions
   - Check if keys are expired

### Debug Commands

```bash
# Check app status
curl https://your-app.onrender.com/health

# Check database connection
# Look at Render logs for database connection errors

# Test OpenAI API
curl -H "Authorization: Bearer YOUR_OPENAI_KEY" \
  https://api.openai.com/v1/models

# Test Pinecone API
curl -H "Api-Key: YOUR_PINECONE_KEY" \
  https://controller.us-east-1-aws.pinecone.io/databases
```

## 📊 Monitoring & Scaling

### Free Tier Limitations

- **Web Service**: 750 hours/month
- **Database**: 90 days max
- **Bandwidth**: 100GB/month

### Upgrade Options

1. **Starter Plan**: $7/month
   - Unlimited hours
   - Better performance
   - Priority support

2. **Standard Plan**: $25/month
   - Auto-scaling
   - Custom domains
   - Advanced monitoring

## 🔒 Security Considerations

1. **Environment Variables**: Never commit API keys to Git
2. **Database Access**: Use Render's managed PostgreSQL
3. **HTTPS**: Automatically enabled on Render
4. **Rate Limiting**: Consider implementing for production use

## 📈 Performance Optimization

1. **Enable Caching**: Add Redis for session storage
2. **CDN**: Use Cloudflare for static assets
3. **Database Indexing**: Optimize PostgreSQL queries
4. **Image Optimization**: Compress uploaded PDFs

## 🎉 Success!

Once deployed, your app will be:
- ✅ **Publicly accessible** via HTTPS
- ✅ **Automatically scaled** based on traffic
- ✅ **Monitored** with built-in logging
- ✅ **Backed up** with managed database

## 📞 Support

- **Render Documentation**: [docs.render.com](https://docs.render.com)
- **Render Community**: [community.render.com](https://community.render.com)
- **GitHub Issues**: Open an issue in your repository

---

**Happy Deploying! 🚀**

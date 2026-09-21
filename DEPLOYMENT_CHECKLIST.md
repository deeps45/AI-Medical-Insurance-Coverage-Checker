# 🚀 Render Deployment Checklist

## ✅ Pre-Deployment Checklist

- [ ] **Code is committed to GitHub**
- [ ] **API keys are ready**:
  - [ ] OpenAI API key (`sk-...`)
  - [ ] Pinecone API key (`pcsk_...`)
- [ ] **Files are in repository**:
  - [ ] `render.yaml`
  - [ ] `Dockerfile`
  - [ ] `backend/` directory
  - [ ] `frontend/` directory

## 🎯 Deployment Steps

### Option 1: Blueprint (Recommended)
1. [ ] Go to [render.com](https://render.com)
2. [ ] Click "New +" → "Blueprint"
3. [ ] Connect GitHub repository
4. [ ] Add environment variables:
   - [ ] `OPENAI_API_KEY`
   - [ ] `PINECONE_API_KEY`
5. [ ] Click "Create New Resources"
6. [ ] Wait for deployment (5-10 minutes)

### Option 2: Manual
1. [ ] Create Web Service
2. [ ] Create PostgreSQL Database
3. [ ] Link database to web service
4. [ ] Add all environment variables
5. [ ] Deploy

## 🔧 Post-Deployment

- [ ] **Test app functionality**:
  - [ ] Upload test PDF
  - [ ] Ask test question
  - [ ] Verify AI responses
- [ ] **Check logs** for errors
- [ ] **Test health endpoint**
- [ ] **Verify database connection**

## 🚨 Common Issues

- [ ] **Build fails** → Check Dockerfile and logs
- [ ] **App won't start** → Verify environment variables
- [ ] **Database issues** → Check connection string
- [ ] **API errors** → Verify API keys

## 📱 Your App URL

Once deployed, your app will be available at:
```
https://ai-medical-insurance-checker.onrender.com
```

## 📞 Need Help?

- Check [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions
- Review Render logs for specific errors
- Open GitHub issue for support

---

**Ready to deploy? Let's go! 🚀**

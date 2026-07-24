$ErrorActionPreference = "Stop"
Write-Host "Setting up frontend in temporary directory..."

if (Test-Path "d:\temp_frontend") {
    Remove-Item -Path "d:\temp_frontend" -Recurse -Force
}

# Initialize Vite React template
npx --yes create-vite@latest d:\temp_frontend --template react

Write-Host "Copying initialized files to frontend directory..."
# Only copy files that we didn't customize. We need package.json and vite files.
# Wait, we customized package.json to add dependencies? No, we didn't use `npm install`.
Copy-Item -Path "d:\temp_frontend\package.json" -Destination "d:\Research_Agent\frontend\package.json" -Force
Copy-Item -Path "d:\temp_frontend\eslint.config.js" -Destination "d:\Research_Agent\frontend\eslint.config.js" -Force
Copy-Item -Path "d:\temp_frontend\vite.config.js" -Destination "d:\Research_Agent\frontend\vite.config.js" -Force -ErrorAction SilentlyContinue

# Ensure the proxy config remains in vite.config.js
$viteConfig = @"
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
"@
Set-Content -Path "d:\Research_Agent\frontend\vite.config.js" -Value $viteConfig

# Clean up temp
Remove-Item -Path "d:\temp_frontend" -Recurse -Force

Write-Host "Installing NPM dependencies..."
cd d:\Research_Agent\frontend
npm install
npm install react-markdown

Write-Host "Frontend setup complete."

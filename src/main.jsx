import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import './index.css'

// Import Amplify configuration
import { Amplify } from 'aws-amplify'
import awsExports from './aws-exports'

// Configure Amplify with your backend settings
Amplify.configure(awsExports)

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
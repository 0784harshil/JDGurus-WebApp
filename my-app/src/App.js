// src/App.js
import React, { useState } from 'react';
import './App.css';
import { BrowserRouter as Router, Route, Routes, Navigate } from 'react-router-dom';
import Login from './Login'; // Default import
import Dashboard from './Dashboard'; // Import Dashboard component
import Inventory from './Inventory'; // Import Inventory component
import BarcodeSelector from './BarcodeSelector'; // Import BarcodeSelector component
import Design1 from './Design1'; // Import Design1 component
import Navbar from './Navbar'; // Import Navbar component
import { Container } from '@mui/material';
import LabelPrinter from './LabelPrinter'; // Import LabelPrinter component
import Signup from './Signup'; // Import Signup component
import EditProfile from './EditProfile'; // Import EditProfile component
import MixAndMatchReport from './MixAndMatchReport'; // Import MixAndMatchReport component

function App() {
    const [isLoggedIn, setIsLoggedIn] = useState(false); // State to manage login status

    const handleLoginSuccess = () => {
        setIsLoggedIn(true); // Update login status on successful login
    };

    const handleSignupSuccess = () => {
        console.log('User profile saved.');
    };

    const handleEditSuccess = () => {
        console.log('User profile updated.');
    };

    return (
        <Router>
            <Navbar isLoggedIn={isLoggedIn} /> {/* Pass isLoggedIn to Navbar */}
            <Container>
                <Routes>
                    <Route path="/" element={<Login onLoginSuccess={handleLoginSuccess} />} />
                    <Route path="/signup" element={<Signup onSignupSuccess={handleSignupSuccess} />} /> {/* New route for Signup */}
                    <Route path="/edit-profile" element={<EditProfile onEditSuccess={handleEditSuccess} />} /> {/* New route for Edit Profile */}
                    <Route path="/dashboard" element={isLoggedIn ? <Dashboard /> : <Navigate to="/" />} />
                    <Route path="/inventory" element={isLoggedIn ? <Inventory /> : <Navigate to="/" />} />
                    <Route path="/barcode-selector" element={<BarcodeSelector />} /> {/* New route for Barcode Selector */}
                    <Route path="/design1" element={<Design1 />} /> {/* New route for Design1 */}
                    <Route path="/label-printer" element={<LabelPrinter />} /> {/* New route for Label Printer */}
                    <Route path="/mix-and-match-report" element={<MixAndMatchReport />} /> {/* New route for Mix and Match Report */}
                    {/* Add more routes as needed */}
                </Routes>
            </Container>
        </Router>
    );
}

export default App;
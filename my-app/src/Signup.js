import React, { useState } from 'react';
import {
    Container,
    Typography,
    TextField,
    Button,
    Snackbar,
    Alert
} from '@mui/material';

const Signup = ({ onSignupSuccess }) => {
    const [serverName, setServerName] = useState('');
    const [databaseName, setDatabaseName] = useState('');
    const [storeId, setStoreId] = useState('');
    const [adminPassword, setAdminPassword] = useState('');
    const [snackbarOpen, setSnackbarOpen] = useState(false);
    const [snackbarMessage, setSnackbarMessage] = useState('');

    const handleSignup = () => {
        // Save the profile information to local storage
        const profile = {
            serverName,
            databaseName,
            storeId,
            adminPassword
        };
        localStorage.setItem('userProfile', JSON.stringify(profile));

        // Call the onSignupSuccess callback to notify the parent component
        onSignupSuccess();

        // Show success message
        setSnackbarMessage('Profile saved successfully!');
        setSnackbarOpen(true);
    };

    const handleSnackbarClose = () => {
        setSnackbarOpen(false);
    };

    return (
        <Container maxWidth="sm" style={{ marginTop: '20px' }}>
            <Typography variant="h4" align="center" gutterBottom>
                Signup
            </Typography>
            <TextField
                label="Server Name"
                variant="outlined"
                fullWidth
                value={serverName}
                onChange={(e) => setServerName(e.target.value)}
                style={{ marginBottom: '20px' }}
            />
            <TextField
                label="Database Name"
                variant="outlined"
                fullWidth
                value={databaseName}
                onChange={(e) => setDatabaseName(e.target.value)}
                style={{ marginBottom: '20px' }}
            />
            <TextField
                label="Store ID"
                variant="outlined"
                fullWidth
                value={storeId}
                onChange={(e) => setStoreId(e.target.value)}
                style={{ marginBottom: '20px' }}
            />
            <TextField
                label="Admin Password"
                type="password"
                variant="outlined"
                fullWidth
                value={adminPassword}
                onChange={(e) => setAdminPassword(e.target.value)}
                style={{ marginBottom: '20px' }}
            />
            <Button 
                variant="contained" 
                color="primary" 
                onClick={handleSignup}
                disabled={!serverName || !databaseName || !storeId || !adminPassword} // Disable if fields are empty
            >
                Save Profile
            </Button>
            <Snackbar open={snackbarOpen} autoHideDuration={6000} onClose={handleSnackbarClose}>
                <Alert onClose={handleSnackbarClose} severity="success" sx={{ width: '100%' }}>
                    {snackbarMessage}
                </Alert>
            </Snackbar>
        </Container>
    );
};

export default Signup;
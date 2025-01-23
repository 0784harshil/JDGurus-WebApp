// src/Login.js
import React, { useState } from 'react';
import {
    Container,
    Typography,
    TextField,
    Button,
    CircularProgress,
    Alert,
    CssBaseline,
    Paper,
} from '@mui/material';
import axios from 'axios';
import { useNavigate } from 'react-router-dom'; // Import useNavigate

const Login = ({ onLoginSuccess }) => {
    const [storeId, setStoreId] = useState('');
    const [adminPass, setAdminPass] = useState('');
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);
    const [success, setSuccess] = useState(false);
    const navigate = useNavigate(); // Initialize useNavigate

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError(null);
        setSuccess(false);
        setLoading(true);

        try {
            const response = await axios.post('http://localhost:5000/api/login', {
                Store_ID: storeId,
                Admin_Pass: adminPass,
            });

            if (response.data.success) {
                // Set session time for half an hour
                const currentTime = new Date().getTime();
                const sessionDuration = 30 * 60 * 1000; // 30 minutes in milliseconds
                localStorage.setItem('isLoggedIn', 'true');
                localStorage.setItem('loginTime', currentTime.toString());

                setSuccess(true);
                setError(null);
                onLoginSuccess(); // Call the function to update login state
                navigate('/dashboard'); // Redirect to Dashboard after successful login
            } else {
                setError(response.data.message);
                setSuccess(false);
            }
        } catch (err) {
            setError('Server error. Please try again later.');
            setSuccess(false);
        } finally {
            setLoading(false);
        }
    };

    return (
        <Container component="main" maxWidth="xs">
            <CssBaseline />
            <Paper elevation={3} style={{ padding: '20px', marginTop: '50px' }}>
                <Typography variant="h5" align="center">
                    Login
                </Typography>
                <form onSubmit={handleSubmit} style={{ marginTop: '20px' }}>
                    <TextField
                        variant="outlined"
                        margin="normal"
                        required
                        fullWidth
                        label="Store ID"
                        value={storeId}
                        onChange={(e) => setStoreId(e.target.value)}
                    />
                    <TextField
                        variant="outlined"
                        margin="normal"
                        required
                        fullWidth
                        label="Admin Password"
                        type="password"
                        value={adminPass}
                        onChange={(e) => setAdminPass(e.target.value)}
                    />
                    {loading ? (
                        <CircularProgress />
                    ) : (
                        <Button
                            type="submit"
                            fullWidth
                            variant="contained"
                            color="primary"
                            style={{ marginTop: '20px' }}
                        >
                            Login
                        </Button>
                    )}
                    {error && <Alert severity="error" style={{ marginTop: '20px' }}>{error}</Alert>}
                    {success && <Alert severity="success" style={{ marginTop: '20px' }}>Login successful!</Alert>}
                </form>
            </Paper>
        </Container>
    );
};

export default Login;
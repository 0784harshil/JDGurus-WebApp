// src/Dashboard.js
import React from 'react';
import { Container, Typography, Grid, Paper } from '@mui/material';
import Inventory from './Inventory'; // Import Inventory component
import BarcodeSelector from './BarcodeSelector'; // Import BarcodeSelector component

const Dashboard = () => {
    return (
        <Container>
            <Typography variant="h4" gutterBottom align="center">
                Dashboard
            </Typography>
            <Grid container spacing={4}>
                <Grid item xs={12}>
                    <Paper elevation={3} style={{ padding: '20px' }}>
                        
                        <Inventory /> {/* Render Inventory component */}
                    </Paper>
                </Grid>
            </Grid>
            <div style={{ margin: '40px 0' }} /> {/* Add space between sections */}
             {/* Custom Header for Barcode Selector */}
             
            <BarcodeSelector /> {/* Render BarcodeSelector component */}
        </Container>
    );
};

export default Dashboard;
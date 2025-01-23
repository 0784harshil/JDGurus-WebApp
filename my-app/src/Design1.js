// src/Design1.js
import React, { useState } from 'react';
import {
    Container,
    Typography,
    TextField,
    Button,
    Paper,
    CssBaseline,
    Alert,
} from '@mui/material';

const Design1 = () => {
    const [item, setItem] = useState('');
    const [quantity, setQuantity] = useState(1);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(false);

    const handlePrintLabel = () => {
        // Basic validation
        if (!item || quantity <= 0) {
            setError('Please enter a valid item and quantity.');
            setSuccess(false);
            return;
        }

        // Here you would typically send the data to the backend to print the label
        // For now, we will just simulate a successful print
        console.log(`Printing label for item: ${item}, Quantity: ${quantity}`);
        setSuccess(true);
        setError(null);

        // Reset the form
        setItem('');
        setQuantity(1);
    };

    return (
        <Container component="main" maxWidth="xs">
            <CssBaseline />
            <Paper elevation={3} style={{ padding: '20px', marginTop: '50px' }}>
                <Typography variant="h5" align="center">
                    Barcode Design 1
                </Typography>
                <TextField
                    variant="outlined"
                    margin="normal"
                    required
                    fullWidth
                    label="Enter Item or Scan Item"
                    value={item}
                    onChange={(e) => setItem(e.target.value)}
                />
                <TextField
                    variant="outlined"
                    margin="normal"
                    required
                    fullWidth
                    type="number"
                    label="Quantity"
                    value={quantity}
                    onChange={(e) => setQuantity(e.target.value)}
                    inputProps={{ min: 1 }}
                />
                {error && <Alert severity="error" style={{ marginTop: '20px' }}>{error}</Alert>}
                {success && <Alert severity="success" style={{ marginTop: '20px' }}>Label printed successfully!</Alert>}
                <Button
                    type="button"
                    fullWidth
                    variant="contained"
                    color="primary"
                    style={{ marginTop: '20px' }}
                    onClick={handlePrintLabel}
                >
                    Print Label
                </Button>
            </Paper>
        </Container>
    );
};

export default Design1;
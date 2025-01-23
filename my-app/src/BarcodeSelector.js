// src/BarcodeSelector.js
import React from 'react';
import { Grid, Card, CardContent, CardMedia, Typography, Button } from '@mui/material';
import { useNavigate } from 'react-router-dom';

const barcodeDesigns = [
    { id: 1, title: 'Design 1', image: 'images/design1.png', route: '/design1' },
    { id: 2, title: 'Design 2', image: 'images/design2.png', route: '/design2' },
    { id: 3, title: 'Design 3', image: 'images/design3.png', route: '/design3' },
    { id: 4, title: 'Design 4', image: 'images/design4.png', route: '/design4' },
    { id: 5, title: 'Design 5', image: 'images/design5.png', route: '/design5' },
    { id: 6, title: 'Design 6', image: 'images/design6.png', route: '/design6' },
];

const BarcodeSelector = () => {
    const navigate = useNavigate();

    return (
        <div>
            {/* Custom Header for Barcode Selector */}
            <Typography variant="h4" gutterBottom align="center" style={{ fontWeight: 'bold' }}>
                CUSTOM BARCODE PRINT
            </Typography>
            <Typography variant="h5" gutterBottom align="center">
                Select Barcode Design
            </Typography>
            <Grid container spacing={4}>
                {barcodeDesigns.map((design) => (
                    <Grid item xs={12} sm={6} md={4} key={design.id}>
                        <Card>
                            <CardMedia
                                component="img"
                                height="140"
                                image={design.image}
                                alt={design.title}
                            />
                            <CardContent>
                                <Typography variant="h5" component="div">
                                    {design.title}
                                </Typography>
                                <Button
                                    variant="contained"
                                    color="primary"
                                    onClick={() => navigate(design.route)}
                                    style={{ marginTop: '10px' }}
                                >
                                    Select
                                </Button>
                            </CardContent>
                        </Card>
                    </Grid>
                ))}
            </Grid>
        </div>
    );
};

export default BarcodeSelector;
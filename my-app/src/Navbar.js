import React from 'react';
import { AppBar, Toolbar, Typography, Button } from '@mui/material';
import { Link } from 'react-router-dom';

const Navbar = ({ isLoggedIn, onLogout }) => {
    return (
        <AppBar position="static" style={{ backgroundColor: '#3f51b5', boxShadow: '0 4px 8px rgba(0, 0, 0, 0.2)' }}>
            <Toolbar style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 20px' }}>
                <Typography variant="h6" style={{ fontWeight: 'bold', color: 'white', fontSize: '1.5rem' }}>
                    JD GURUS
                </Typography>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                    <Button 
                        color="inherit" 
                        component={Link} 
                        to="/dashboard" 
                        style={{ marginLeft: '15px', color: '#ffeb3b', transition: 'background-color 0.3s ease' }}
                        onMouseEnter={(e) => e.currentTarget.style.color = '#ffc107'} // Hover color
                        onMouseLeave={(e) => e.currentTarget.style.color = '#ffeb3b'} // Reset color
                    >
                        Dashboard
                    </Button>
                    <Button 
                        color="inherit" 
                        component={Link} 
                        to="/inventory" 
                        style={{ marginLeft: '15px', color: '#ffeb3b', transition: 'background-color 0.3s ease' }}
                        onMouseEnter={(e) => e.currentTarget.style.color = '#ffc107'} // Hover color
                        onMouseLeave={(e) => e.currentTarget.style.color = '#ffeb3b'} // Reset color
                    >
                        Inventory
                    </Button>

                    <Button 
                        color="inherit" 
                        component={Link} 
                        to="/barcode-selector" // Link to BarcodeSelector
                        style={{ marginLeft: '15px', color: '#ffeb3b', transition: 'background-color 0.3s ease' }}
                        onMouseEnter={(e) => e.currentTarget.style.color = '#ffc107'} // Hover color
                        onMouseLeave={(e) => e.currentTarget.style.color = '#ffeb3b'} // Reset color
                    >
                        Barcode Selector
                    </Button>
                
                   
                </div>
            </Toolbar>
        </AppBar>
    );
};

export default Navbar;
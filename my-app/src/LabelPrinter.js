import React, { useEffect, useState } from 'react';
import axios from 'axios';
import {
    Container,
    Typography,
    TextField,
    Button,
    List,
    ListItem,
    ListItemText,
    ListItemSecondaryAction,
    Snackbar,
    Alert
} from '@mui/material';

const LabelPrinter = () => {
    const [labelData, setLabelData] = useState([]);
    const [printerIp, setPrinterIp] = useState('');
    const [itemNum, setItemNum] = useState(''); // State for item number input
    const [quantity, setQuantity] = useState(1); // State for quantity input
    const [selectedItem, setSelectedItem] = useState(null); // State for selected item
    const [snackbarOpen, setSnackbarOpen] = useState(false);
    const [snackbarMessage, setSnackbarMessage] = useState('');

    useEffect(() => {
        const fetchLabelData = async () => {
            try {
                const response = await axios.get('http://127.0.0.1:5000/api/label_data');
                // Ensure price is treated as a number
                const formattedData = response.data.map(item => ({
                    ...item,
                    price: parseFloat(item.price) // Convert price to a number
                }));
                setLabelData(formattedData);
            } catch (error) {
                console.error('Error fetching label data:', error);
            }
        };

        fetchLabelData();
    }, []);

    const handleItemNumChange = (e) => {
        const inputItemNum = e.target.value;
        setItemNum(inputItemNum);

        // Find the item based on itemNum
        const foundItem = labelData.find(item => item.itemNum === inputItemNum);
        setSelectedItem(foundItem || null);

        // Debugging: Print the selected item data
        if (foundItem) {
            console.log('Selected Item:', foundItem);
        } else {
            console.log('Item not found for itemNum:', inputItemNum);
        }
    };

    const printLabel = () => {
        if (!selectedItem) {
            setSnackbarMessage('Item not found.');
            setSnackbarOpen(true);
            return;
        }

        const zpl = `
            ^XA
            ^PW400
            ^LL200
            ^FO10,10^A0N,30,30^FDItem Number: ${selectedItem.itemNum}^FS
            ^FO10,50^A0N,30,30^FDItem Name: ${selectedItem.itemName}^FS
            ^FO10,100^BY2,2,50
            ^BCN,N,N,N,N,D^FD${selectedItem.itemName}^FS
            ^FO10,170^A0N,25,25^FDPrice: $${selectedItem.price.toFixed(2)}^FS
            ^XZ
        `;

        // Print the specified quantity of labels
        for (let i = 0; i < quantity; i++) {
            const printUrl = `http://${printerIp}/zpl`;

            axios.post(printUrl, zpl, {
                headers: {
                    'Content-Type': 'text/plain',
                },
            })
            .then(response => {
                setSnackbarMessage(`Label sent to printer successfully! (${i + 1}/${quantity})`);
                setSnackbarOpen(true);
            })
            .catch(error => {
                console.error('Error sending label to printer:', error);
                setSnackbarMessage('Error sending label to printer.');
                setSnackbarOpen(true);
            });
        }
    };

    const handleSnackbarClose = () => {
        setSnackbarOpen(false);
    };

    return (
        <Container maxWidth="sm" style={{ marginTop: '20px' }}>
            <Typography variant="h4" align="center" gutterBottom>
                Label Printer
            </Typography>
            <TextField
                label="Printer IP Address"
                variant="outlined"
                fullWidth
                value={printerIp}
                onChange={(e) => setPrinterIp(e.target.value)}
                style={{ marginBottom: '20px' }}
            />
            <TextField
                label="Item Number"
                variant="outlined"
                fullWidth
                value={itemNum}
                onChange={handleItemNumChange}
                style={{ marginBottom: '20px' }}
            />
            {selectedItem && (
                <div>
                    <Typography variant="h6" gutterBottom>
                        Selected Item: {selectedItem.itemName} - ${selectedItem.price.toFixed(2)}
                    </Typography>
                </div>
            )}
            <TextField
                label="Quantity"
                type="number"
                variant="outlined"
                fullWidth
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                style={{ marginBottom: '20px' }}
                inputProps={{ min: 1 }} // Prevent negative or zero values
            />
            <Button 
                variant="contained" 
                color="primary" 
                onClick={printLabel}
                disabled={!selectedItem} // Disable if no item is selected
            >
                Print Label
            </Button>
            <Snackbar open={snackbarOpen} autoHideDuration={6000} onClose={handleSnackbarClose}>
                <Alert onClose={handleSnackbarClose} severity="success" sx={{ width: '100%' }}>
                    {snackbarMessage}
                </Alert>
            </Snackbar>
        </Container>
    );
};

export default LabelPrinter;
import React, { useEffect, useState } from 'react';
import axios from 'axios';

const Customers = () => {
    const [customers, setCustomers] = useState([]);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchCustomers = async () => {
            try {
                const response = await axios.get('http://localhost:5000/api/customers'); // Update with your customer API endpoint
                setCustomers(response.data);
            } catch (err) {
                setError(err.message);
            }
        };

        fetchCustomers();
    }, []);

    if (error) {
        return <div>Error: {error}</div>;
    }

    return (
        <div>
            <h1>Customers</h1>
            <ul>
                {customers.map(customer => (
                    <li key={customer.id}>
                        {customer.name} - Email: {customer.email}
                    </li>
                ))}
            </ul>
        </div>
    );
};

export default Customers;

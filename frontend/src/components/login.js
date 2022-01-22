import React, {Component, useEffect, useState} from 'react';
import { globalState } from '../state';
import {Redirect} from "react-router-dom";

export default function Login() {

    console.log('login component says hi');
    return (
        <div className='card'>
            <div className='card-header'>
                <h2 className='card-title text-primary text-center'>Login with Discord</h2>
            </div>
            <div className='card-body'>
                <a href='/api/auth/discord'>
                    <img src='https://dejay.dev/assets/discord.svg' height='256' width='256' style={{
                        margin: 'auto',
                        display: 'block',
                    }}/>
                </a>
            </div>
        </div>
    );

}

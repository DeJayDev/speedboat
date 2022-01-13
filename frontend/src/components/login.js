import React, { useState, useEffect } from 'react';
import { Redirect } from 'react-router-dom'
import {globalState} from '../state';

export default function Login(props) {

  const [user, setUser] = useState(globalState.user);

  useEffect(() => {
    globalState.events.on('user.set', (user) => {
      setUser(user);
    });

    globalState.init();
  }, []);

  if (user) {
    return <Redirect to='/' />;
  }

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
          }} />
        </a>
      </div>
    </div>
  );
}

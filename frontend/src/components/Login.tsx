import React from 'react';

function Login() {

  return (
    <div className='card'>
      <div className='card-header'>
        <h2 className='card-title text-primary text-center'>Login with Discord</h2>
      </div>
      <div className='card-body'>
        <a href='/api/auth/discord'>
          <img src='https://assets-global.website-files.com/6257adef93867e50d84d30e2/636e0b5061df29d55a92d945_full_logo_blurple_RGB.svg' height='256' width='256' style={{
            margin: 'auto',
            display: 'block',
          }} />
        </a>
      </div>
    </div>
  );

}

export default Login;
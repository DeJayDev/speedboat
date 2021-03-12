var path = require('path');

let proxyURL = 'http://localhost:8686';

if (process.env.NODE_ENV == 'docker') {
    proxyURL = 'http://web:8686';
}

module.exports = {
    // entry file - starting point for the app
    entry: './src',

    // where to dump the output of a production build
    output: {
        path: path.join(__dirname, 'src'),
        filename: 'bundle.js'
    },

    module: {
        rules: [
            {
                test: /\.css$/,
                loader: 'css-loader',
                options: {
                    modules: {
                        localIdentName: '[name]'
                    }
                }
            },
            {
                test: /\.jsx?/i,
                loader: 'babel-loader',
                options: {
                    presets: [
                        '@babel/preset-env'
                    ],
                    plugins: [
                        ['@babel/transform-react-jsx']
                    ]
                }
            }
        ]
    },

    devServer: {
        host: '0.0.0.0',
        disableHostCheck: true,
        // serve up any static files from src/
        contentBase: path.join(__dirname, 'src'),

        // enable gzip compression:
        compress: true,

        // enable pushState() routing, as used by preact-router et al:
        historyApiFallback: true,

        proxy: {
            '/api': {
                target: proxyURL,
                secure: false
            }
        }
    },

    resolve: {
        alias: {
            config: path.join(__dirname, 'src', 'config', process.env.NODE_ENV || 'development')
        }
    }

    // resolve: {
    // 		alias: {
    // 				'react': 'preact-compat',
    // 				'react-dom': 'preact-compat',
    // 				// Not necessary unless you consume a module using `createClass`
    // 				'create-react-class': 'preact-compat/lib/create-react-class'
    // 		}
    // }

};
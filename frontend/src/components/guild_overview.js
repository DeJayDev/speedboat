import React, { Component } from 'react';
import {globalState} from '../state';

function GuildWidget(props) {
  const source = `https://discord.com/api/guilds/${props.guildID}/widget.png?style=banner2`;
  return (<img src={source} alt='(Guild must have widget enabled)' />);
}

function GuildIcon(props) {
  if (props.guildIcon) {
    const source = `https://cdn.discordapp.com/icons/${props.guildID}/${props.guildIcon}.png`;
    return <img src={source} alt='No Icon' />;
  } else {
    return <i>No Icon</i>;
  }
}

function GuildSplash(props) {
  if (props.guildSplash) {
    const source = `https://cdn.discordapp.com/splashes/${props.guildID}/${props.guildSplash}.png`;
    return <img src={source} alt='No Splash' />;
  } else {
    return <i>No Splash</i>;
  }
}

function GuildOverviewInfoTable(props) {
  return (
    <table className='table table-striped table-bordered'>
      <thead></thead>
      <tbody>
        <tr>
          <td>ID</td>
          <td>{props.guild.id}</td>
        </tr>
        <tr>
          <td>Owner</td>
          <td>{props.guild.ownerID}</td>
        </tr>
        <tr>
          <td>Region</td>
          <td>{props.guild.region}</td>
        </tr>
        <tr>
          <td>Icon</td>
          <td><GuildIcon guildID={props.guild.id} guildIcon={props.guild.icon} /></td>
        </tr>
        <tr>
          <td>Splash</td>
          <td><GuildSplash guildID={props.guild.id} guildSplash={props.guild.splash} /></td>
        </tr>
      </tbody>
    </table>
  );
}

export default class GuildOverview extends Component {
  constructor() {
    super();

    this.state = {
      guild: null,
    };
  }

  ensureGuild() {
    globalState.getGuild(this.props.match.params.gid).then((guild) => {
      guild.events.on('update', (guild) => this.setState({guild}));
      globalState.currentGuild = guild;
      this.setState({guild});
    }).catch((err) => {
      console.error('Failed to load guild', this.props.match.params.gid, err);
    });
  }

  componentWillUnmount() {
    globalState.currentGuild = null;
  }

  render() {
    if (!this.state.guild || this.state.guild.id != this.props.match.params.gid) {
      this.ensureGuild();
      return <h3>Loading...</h3>;
    }

    return (<div>
      <div className='row'>
        <div className='col-lg-12'>
          <div className='card'>
            <div className='card-header'>Guild Banner</div>
            <div className='card-body'>
              <GuildWidget guildID={this.state.guild.id} />
            </div>
          </div>
          <div className='card'>
            <div className='card-header'>Guild Info</div>
            <div className='card-body'>
              <div className='table-responsive'>
                <GuildOverviewInfoTable guild={this.state.guild} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>);
  }
}

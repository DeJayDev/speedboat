import React, { useEffect, useState } from 'react';
import { useRoute } from 'wouter';
import Guild from '../types/guild';

function GuildWidget() {
  const [match, params] = useRoute("/guilds/:gid");

  const source = `https://discord.com/api/guilds/${params?.gid}/widget.png?style=banner2`;
  return (<img src={source} alt='(Guild must have widget enabled)' />);
}

function GuildIcon(props: {guild: Guild}) {
  const [match, params] = useRoute("/guilds/:gid");

  return <img src={props.guild.iconURL} />;
}

function GuildSplash(props: {guild: Guild}) {
  const [match, params] = useRoute("/guilds/:gid");

  if (props.guild.splash) {
    return <img src={props.guild.splashURL} alt='No Splash' />;
  } else {
    return <i>No Splash</i>;
  }
}

function GuildInfoTable(props: {guild: Guild}) {

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
          <td>{props.guild.owner}</td>
        </tr>
        <tr>
          <td>Icon</td>
          <td><GuildIcon guild={props.guild}/></td>
        </tr>
        <tr>
          <td>Splash</td>
          <td><GuildSplash guild={props.guild} /></td>
        </tr>
      </tbody>
    </table>
  );
}

export default function GuildOverview() {
  const [match, params] = useRoute("/guilds/:gid");
  const [guild, setGuild] = useState<Guild>();

  function ensureGuild() {
    Guild.fromID(params?.gid!!).then(g => setGuild(g));
  }

  useEffect(() => {
    if(!guild) {
      ensureGuild();
    }
  }, [params]);

  if (!guild) {
    ensureGuild();
    return <h3>Loading...</h3>;
  }

  return (<div>
    <div className='row'>
      <div className='col-lg-12'>
        <div className='card'>
          <div className='card-header'>Guild Banner</div>
          <div className='card-body'>
            <GuildWidget/>
          </div>
        </div>
        <div className='card'>
          <div className='card-header'>Guild Info</div>
          <div className='card-body'>
            <div className='table-responsive'>
              <GuildInfoTable guild={guild} />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>);

}

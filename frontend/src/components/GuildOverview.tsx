import React, { useEffect, useState } from 'react';
import { useRoute } from 'wouter';
import Guild from '../types/guild';
import { Card, Grid, Italic, Table, TableBody, TableCell, TableRow, Text, Title } from '@tremor/react';

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

  return (
    <div>
      <Grid className="gap-6 mt-6">
        <Title>Info for {guild.name}</Title>
        <Card>
          <Text>Guild Banner</Text>
          <img src={`https://discord.com/api/guilds/${guild.id}/widget.png?style=banner2`}/>
        </Card>
        <Card>
          <Text>Guild Info</Text>
          <GuildInfoTable guild={guild} />
        </Card>
      </Grid>
    </div>
  );

function GuildInfoTable(props: {guild: Guild}) {
  return (
    <Table>
      <TableBody>
        <TableRow>
          <TableCell>ID</TableCell>
          <TableCell>{props.guild.id}</TableCell>
        </TableRow>
        <TableRow>
          <TableCell>Owner</TableCell>
          <TableCell>{props.guild.owner}</TableCell>
        </TableRow>
        <TableRow>
          <TableCell>Region</TableCell>
          <TableCell>{props.guild.region}</TableCell>
        </TableRow>
        <TableRow>
          <TableCell>Icon</TableCell>
          <TableCell>
            <img src={props.guild.iconURL} alt=''/>
          </TableCell>
        </TableRow>
        <TableRow>
          <TableCell>Splash</TableCell>
          <TableCell>
            {props.guild.splash ? <img src={props.guild.splashURL} alt=''/> : <Italic>No Splash</Italic>}
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>
  );
}

}

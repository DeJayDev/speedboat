import React, { useEffect, useState } from 'react';
import AceEditor from 'react-ace';

import ace from 'ace-builds/src-noconflict/ace';
import yamlWorkerURL from 'ace-builds/src-noconflict/worker-yaml?url';

ace.config.setModuleUrl('ace/mode/yaml_worker', yamlWorkerURL);

import 'ace-builds/src-min-noconflict/mode-yaml';
import 'ace-builds/src-min-noconflict/theme-monokai';
import Guild from '../types/guild';
import { useRoute } from 'wouter';
import { FaCheck } from 'react-icons/fa';

function GuildConfig() {
  const [message, setMessage] = useState({});
  const [messageTimer, setMessageTimer] = useState(0);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  const [match, params] = useRoute("/guilds/:gid/config");
  const [guild, setGuild] = useState<Guild>();

  const [initialConfig, setInitialConfig] = useState("");
  const [newConfig, setNewConfig] = useState(initialConfig);

  useEffect(() => {
    if(!match) return;
    Guild.fromID(params?.gid!!).then(async g => {
      setGuild(g)
      const config = await g.getConfig();
      setInitialConfig(config);
      setNewConfig(config);
    });
  }, [params?.gid]);

  function onEditorChange(newValue: string) {
    setNewConfig(newValue);
    setHasUnsavedChanges(false);
    if (initialConfig != newValue) {
      setHasUnsavedChanges(true)
    }
  }

  function onSave() {
    guild?.setConfig(newConfig).then(() => {
      setInitialConfig(newConfig);
      setHasUnsavedChanges(false);
      renderMessage('success', 'Saved Configuration!');
    }).catch((err: any) => {
      renderMessage('danger', `Failed to save configuration: ${err}`);
    });
  }

  function renderMessage(type: 'success' | 'danger', contents: string) {
    setMessage({
      type: type,
      contents: contents,
    });

    if (messageTimer) clearTimeout(messageTimer);

    setMessageTimer(setTimeout(() => {
      setMessage("");
      setMessageTimer(0);
    }, 5000));
  }

  return (
    <div>
      <div className='card'>
        <div className='card-header'>
          Configuration Editor
        </div>
        <div className='card-body'>
          <AceEditor
            mode='yaml'
            theme='monokai'
            width='100%'
            height='75vh'
            value={newConfig == null ? '' : newConfig}
            onChange={(newValue) => onEditorChange(newValue)}
          />
        </div>
        <div className='card-footer'>
          {
            guild && guild.role != 'viewer' &&
            <button onClick={() => onSave()} type='button' className='btn btn-success btn-circle btn-lg'>
              <FaCheck/>
            </button>
          }
          {hasUnsavedChanges && <i style={{ paddingLeft: '10px' }}>Unsaved Changes!</i>}
        </div>
      </div>
    </div>
  );
}

export default GuildConfig;

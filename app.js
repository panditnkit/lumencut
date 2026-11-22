// LumenCut Luxury Engine & Video-Aware AI Social Auto-Publisher
document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const videoUrlInput = document.getElementById('video-url');
  const clearBtn = document.getElementById('clear-btn');
  const generateBtn = document.getElementById('generate-btn');
  const sampleChips = document.querySelectorAll('.sample-chip');
  const captionStyleSelect = document.getElementById('caption-style');
  const languageSelect = document.getElementById('language-select');
  const progressContainer = document.getElementById('progress-container');
  const progressBarFill = document.getElementById('progress-bar-fill');
  const progressPercent = document.getElementById('progress-percent');
  const progressPhase = document.getElementById('progress-phase');
  const clipCards = document.querySelectorAll('.clip-card');
  const captionOverlay = document.getElementById('captions-overlay');
  const captionText = document.getElementById('caption-text');
  const togglePlayBtn = document.getElementById('toggle-play-btn');
  const exportBtn = document.getElementById('export-single-btn');
  const tabBtns = document.querySelectorAll('.tab-btn');

  // Account Bar Elements
  const ytToggleBtn = document.getElementById('yt-toggle-btn');
  const igToggleBtn = document.getElementById('ig-toggle-btn');
  const ytCard = document.getElementById('yt-channel-card');
  const igCard = document.getElementById('ig-channel-card');
  const navConnectBtn = document.getElementById('nav-connect-btn');

  // Modal Elements
  const scheduleModal = document.getElementById('schedule-modal');
  const modalCloseBtn = document.getElementById('modal-close-btn');
  const modalCancelBtn = document.getElementById('modal-cancel-btn');
  const confirmScheduleBtn = document.getElementById('confirm-schedule-btn');
  const modalTriggerBtn = document.getElementById('modal-trigger-btn');
  const modalClipTitle = document.getElementById('modal-clip-title');
  const modalClipCaption = document.getElementById('modal-clip-caption');
  const generateHashtagsBtn = document.getElementById('generate-hashtags-btn');
  const modalYtBox = document.getElementById('modal-yt-box');
  const modalIgBox = document.getElementById('modal-ig-box');
  const trendingPillsPreview = document.getElementById('trending-pills-preview');
  const queueGrid = document.getElementById('queue-grid');
  const toastNotice = document.getElementById('toast-notice');
  const toastMsg = document.getElementById('toast-msg');

  // Video-Aware Sample Data (Context-Tailored Captions & Live Trending Tags)
  const sampleData = {
    gaming: {
      url: 'https://youtube.com/watch?v=valorant_champions_final_live_vod',
      clips: [
        {
          id: 1,
          title: '"Wait, watch this insane 1v4 clutch!"',
          hook: 'Sudden audio spike + reaction shout (0:12)',
          words: ['WAIT,', 'WATCH', 'THIS', 'INSANE', '1v4', 'CLUTCH!'],
          avatar: '😎',
          score: '98/100',
          duration: '0:48',
          tags: ['High Energy', 'Chat Spike', 'AI Meta Ready'],
          topic: 'Valorant Clutch',
          autoCaption: `Can you believe this 1v4 clutch?! 💀 Hands were literally shaking in the final 1v1. Tag that teammate who always panics under pressure 👇🔥\n\n#valorant #clutch #gamingreels #esports #1v4 #gamingcommunity #gamer #fps #twitchclips #shorts #reels`,
          hashtagsList: ['#valorant', '#clutch', '#1v4', '#gamingreels', '#esports', '#shorts', '#reels', '#viralgaming']
        },
        {
          id: 2,
          title: '"Bhai ye aim kese laga be?"',
          hook: 'Flick reaction kill (04:15)',
          words: ['BHAI', 'YE', 'AIM', 'KESE', 'LAGA', 'BE?'],
          avatar: '😲',
          score: '95/100',
          duration: '0:32',
          tags: ['Hinglish', 'Insane Aim', 'AI Meta Ready'],
          topic: 'BGMI Flick Headshot',
          autoCaption: `Sensitivity settings link in bio! 🎯 Kya ye lucky flick shot tha ya pure muscle memory? Comment your sensitivity below 👇\n\n#bgmi #aimgod #headshot #pubgmobile #gamingindia #streamer #hinglish #viralreels #reelsindia`,
          hashtagsList: ['#bgmi', '#aimgod', '#headshot', '#pubgmobile', '#streamer', '#hinglish', '#reelsindia']
        },
        {
          id: 3,
          title: '"Pure lobby ka sabse funny whiff"',
          hook: 'Chat laugh frequency spike + mic clipping',
          words: ['WHAT', 'WAS', 'THAT', 'WHIFF', 'BRO?!'],
          avatar: '🤣',
          score: '91/100',
          duration: '0:45',
          tags: ['Comedy', 'Reactions', 'AI Meta Ready'],
          topic: 'Whiff & Fail Reaction',
          autoCaption: `Lagta hai mouse disconnect ho gaya tha lol! 😂 30 bullets and not a single hit. Drop a like if you laughed! Subscribe for daily fails.\n\n#funnygaming #whiff #gamingfails #twitchfails #gamermemes #comedyreels #streamer #lol`,
          hashtagsList: ['#funnygaming', '#whiff', '#gamingfails', '#twitchfails', '#comedyreels', '#streamer']
        }
      ]
    },
    podcast: {
      url: 'https://youtube.com/watch?v=tech_ai_breakthrough_interview',
      clips: [
        {
          id: 1,
          title: '"The #1 mistake beginner creators make..."',
          hook: 'High insight index + tone shift (12:40)',
          words: ['NEVER', 'POST', 'WITHOUT', 'A', 'STRONG', 'HOOK!'],
          avatar: '🎙️',
          score: '97/100',
          duration: '0:55',
          tags: ['Educational', 'Creator Advice', 'AI Meta Ready'],
          topic: 'Creator Growth Advice',
          autoCaption: `Stop posting without a 3-second hook. 🧠 Your video might be gold, but if no one stops scrolling, you get 0 views. Save this for your next video! 👇\n\n#contentcreator #creatoradvice #growthtips #socialmediatips #videoediting #reelsgrowth #podcastclips #shorts`,
          hashtagsList: ['#contentcreator', '#creatoradvice', '#growthtips', '#socialmediatips', '#podcastclips', '#reelsgrowth']
        },
        {
          id: 2,
          title: '"AI agle 2 saal me sab badal dega."',
          hook: 'Controversial statement (28:15)',
          words: ['AI', 'WILL', 'CHANGE', 'EVERYTHING', 'SOON.'],
          avatar: '💡',
          score: '93/100',
          duration: '0:42',
          tags: ['Hinglish', 'Future Tech', 'AI Meta Ready'],
          topic: 'AI Disruption Insights',
          autoCaption: `Agle 2 saal me jo AI tools use nahi karega, wo race se bahar ho jayega. 🚀 Do you agree with this prediction? Share your thoughts below! 👇\n\n#futuretech #artificialintelligence #techpodcast #automation #ai #techindia #careertips #businessgrowth`,
          hashtagsList: ['#futuretech', '#artificialintelligence', '#techpodcast', '#automation', '#ai', '#careertips']
        },
        {
          id: 3,
          title: '"How I made $10,000 in my first month"',
          hook: 'Monetary proof hook (45:10)',
          words: ['FIRST', 'TEN', 'THOUSAND', 'DOLLARS', 'ONLINE.'],
          avatar: '💰',
          score: '90/100',
          duration: '0:58',
          tags: ['Money', 'Case Study', 'AI Meta Ready'],
          topic: 'Online Business Case Study',
          autoCaption: `The exact blueprint I used to reach $10,000 online in 30 days. No fluff, just pure execution. Check the full breakdown on YouTube! 📈\n\n#entrepreneurship #sidehustle #onlinebusiness #financialfreedom #casestudy #wealthmindset #hustle`,
          hashtagsList: ['#entrepreneurship', '#sidehustle', '#onlinebusiness', '#casestudy', '#wealthmindset']
        }
      ]
    },
    esports: {
      url: 'https://twitch.tv/videos/bgmi_grand_finals_day3',
      clips: [
        {
          id: 1,
          title: '"ZONE 6 MEIN 1V3 SURVIVAL!"',
          hook: 'Caster scream + grenade kill explosion',
          words: ['WHAT', 'A', 'NADE', 'BY', 'JONATHAN!'],
          avatar: '🏆',
          score: '99/100',
          duration: '0:40',
          tags: ['BGMI', 'Esports', 'AI Meta Ready'],
          topic: 'BGMI Grand Finals Clutch',
          autoCaption: `THAT GRENADE THROW WAS ILLEGAL! 💥 Jonathan single-handedly wipes the squad in Zone 6. Who is the GOAT of Indian esports? Drop your answer! 🔥\n\n#bgmi #esports #jonathangaming #bgmigrandfinals #pubgmobile #tournament #highlights #reelsindia`,
          hashtagsList: ['#bgmi', '#esports', '#jonathangaming', '#bgmigrandfinals', '#tournament', '#highlights']
        },
        {
          id: 2,
          title: '"Aise rotate karoge toh chicken pakka"',
          hook: 'Tactical analysis point (19:30)',
          words: ['SMOKE', 'AUR', 'VEHICLE', 'COVER', 'USE', 'KARO!'],
          avatar: '🔥',
          score: '94/100',
          duration: '0:38',
          tags: ['Tips & Tricks', 'Hinglish', 'AI Meta Ready'],
          topic: 'Esports Zone Rotation Strategy',
          autoCaption: `Grand Finals level rotation guide. 🚙 Smoke screens + vehicle hard-covers can save your team 9 out of 10 times. Tag your IGL! 👇\n\n#bgmitips #esportscoaching #gameplayguide #rotation #chickenwinner #pubgindia #strategy`,
          hashtagsList: ['#bgmitips', '#esportscoaching', '#gameplayguide', '#rotation', '#pubgindia']
        },
        {
          id: 3,
          title: '"Last man standing wins the trophy!"',
          hook: 'Final kill reaction + crowd cheer',
          words: ['CHAMPIONS', 'OF', 'THE', 'TOURNAMENT!'],
          avatar: '🥇',
          score: '92/100',
          duration: '0:50',
          tags: ['Trophy Moment', 'Grand Final', 'AI Meta Ready'],
          topic: 'Trophy Winning Moment',
          autoCaption: `THE CROWD WENT ABSOLUTELY CRAZY! 🏆 What an emotional victory for the boys. Pure goosebumps moment! Drop ❤️ for the champions.\n\n#champions #trophy #esportstournament #grandfinals #victory #gaminghistory #esportsindia`,
          hashtagsList: ['#champions', '#trophy', '#esportstournament', '#grandfinals', '#victory']
        }
      ]
    }
  };

  let activeData = sampleData.gaming;
  let currentClipIndex = 0;
  let wordAnimationTimer = null;
  let isPlaying = true;

  // Show Toast
  function showToast(message, icon = '🚀') {
    toastMsg.textContent = message;
    document.querySelector('.toast-icon').textContent = icon;
    toastNotice.classList.add('show');
    setTimeout(() => {
      toastNotice.classList.remove('show');
    }, 3500);
  }

  // Account Toggle Handlers
  let ytConnected = true;
  let igConnected = true;

  function toggleYt() {
    ytConnected = !ytConnected;
    if (ytConnected) {
      ytCard.classList.add('connected');
      ytCard.querySelector('.channel-status').className = 'channel-status status-live';
      ytCard.querySelector('.channel-status').textContent = '● YouTube Shorts Active';
      ytToggleBtn.textContent = 'Manage';
      showToast('YouTube Channel linked successfully! (YouTube Data API v3)', '▶');
    } else {
      ytCard.classList.remove('connected');
      ytCard.querySelector('.channel-status').className = 'channel-status';
      ytCard.querySelector('.channel-status').textContent = 'Disconnected';
      ytToggleBtn.textContent = 'Connect';
      showToast('YouTube Channel disconnected.', 'ℹ️');
    }
  }

  function toggleIg() {
    igConnected = !igConnected;
    if (igConnected) {
      igCard.classList.add('connected');
      igCard.querySelector('.channel-status').className = 'channel-status status-live';
      igCard.querySelector('.channel-status').textContent = '● Instagram Reels Active';
      igToggleBtn.textContent = 'Manage';
      showToast('Instagram Account linked successfully! (Meta Graph API)', '📸');
    } else {
      igCard.classList.remove('connected');
      igCard.querySelector('.channel-status').className = 'channel-status';
      igCard.querySelector('.channel-status').textContent = 'Disconnected';
      igToggleBtn.textContent = 'Connect';
      showToast('Instagram Account disconnected.', 'ℹ️');
    }
  }

  ytToggleBtn.addEventListener('click', toggleYt);
  igToggleBtn.addEventListener('click', toggleIg);

  navConnectBtn.addEventListener('click', () => {
    showToast('Social Accounts Hub: Both YouTube and Instagram APIs are active & ready to schedule.', '🔗');
  });

  // Clear Input
  clearBtn.addEventListener('click', () => {
    videoUrlInput.value = '';
    videoUrlInput.focus();
  });

  // Tab Switcher
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tab = btn.dataset.tab;
      if (tab === 'upload') {
        videoUrlInput.placeholder = 'Select local .mp4, .mkv, or .mov video file...';
        videoUrlInput.value = 'C:/Videos/my_raw_stream_2026.mp4';
      } else {
        videoUrlInput.placeholder = 'Paste YouTube, Twitch, Kick link or stream VOD...';
        videoUrlInput.value = activeData.url;
      }
    });
  });

  // Sample Chips Click
  sampleChips.forEach(chip => {
    chip.addEventListener('click', () => {
      const type = chip.dataset.sample;
      if (sampleData[type]) {
        activeData = sampleData[type];
        videoUrlInput.value = activeData.url;
        applyClipsData(activeData.clips);
      }
    });
  });

  // Apply Clips Data to UI
  function applyClipsData(clips) {
    clipCards.forEach((card, idx) => {
      if (clips[idx]) {
        const item = clips[idx];
        card.querySelector('.clip-title').textContent = item.title;
        card.querySelector('.clip-hook').innerHTML = `<strong>Hook:</strong> ${item.hook}`;
        card.querySelector('.virality-score').textContent = item.score;
        card.querySelector('.duration-badge').textContent = item.duration;

        const tagsContainer = card.querySelector('.clip-tags');
        tagsContainer.innerHTML = item.tags.map(t => `<span class="tag ${t.includes('AI') ? 'tag-green' : ''}">${t}</span>`).join('');
      }
    });

    currentClipIndex = 0;
    selectClip(0);
  }

  // Generate Simulation
  generateBtn.addEventListener('click', () => {
    const url = videoUrlInput.value.trim();
    if (!url) {
      alert('Please enter a stream or video URL first!');
      return;
    }

    generateBtn.disabled = true;
    generateBtn.querySelector('.btn-text').textContent = 'Processing...';
    progressContainer.style.display = 'block';

    let percent = 0;
    progressBarFill.style.width = '0%';
    progressPercent.textContent = '0%';

    const steps = [
      { at: 15, text: '⚡ Extracting audio track with yt-dlp...', stepId: 'step-1' },
      { at: 35, text: '🎙️ Whisper STT transcribing full audio speech...', stepId: 'step-2' },
      { at: 65, text: '🔥 Ollama LLM scoring viral moments & emotional peaks...', stepId: 'step-3' },
      { at: 85, text: '📱 Reframing to 9:16 with YOLO facecam split...', stepId: 'step-4' },
      { at: 98, text: '✨ Generating contextual captions & live trending hashtags...', stepId: 'step-5' }
    ];

    const interval = setInterval(() => {
      percent += 2;
      if (percent > 100) percent = 100;

      progressBarFill.style.width = `${percent}%`;
      progressPercent.textContent = `${percent}%`;

      const currentStep = steps.find(s => percent <= s.at);
      if (currentStep) {
        progressPhase.textContent = currentStep.text;
        document.querySelectorAll('.pipeline-steps .step').forEach(st => st.classList.remove('step-active'));
        const stepEl = document.getElementById(currentStep.stepId);
        if (stepEl) stepEl.classList.add('step-active');
      }

      if (percent >= 100) {
        clearInterval(interval);
        progressPhase.textContent = '✅ 3 Clips Generated with Contextual Captions & Trending Tags!';
        document.querySelectorAll('.pipeline-steps .step').forEach(st => st.classList.add('step-done'));

        setTimeout(() => {
          generateBtn.disabled = false;
          generateBtn.querySelector('.btn-text').textContent = 'Generate Clips';
          document.getElementById('results-dashboard').scrollIntoView({ behavior: 'smooth' });
          showToast('Clips + Contextual Captions & Trending Tags Ready!', '✨');
        }, 500);
      }
    }, 35);
  });

  // Clip Selection
  clipCards.forEach((card, index) => {
    card.addEventListener('click', (e) => {
      if (e.target.closest('.open-schedule-modal-btn')) return;
      selectClip(index);
    });
  });

  function selectClip(index) {
    clipCards.forEach(c => c.classList.remove('active'));
    clipCards[index].classList.add('active');
    currentClipIndex = index;

    const clip = activeData.clips[index];
    const avatarFace = document.querySelector('.avatar-face');
    if (avatarFace) avatarFace.textContent = clip.avatar;

    // Reset Caption Word Animation
    startCaptionAnimation(clip.words);
  }

  // Subtitle Word Animation Loop
  function startCaptionAnimation(words) {
    if (wordAnimationTimer) clearInterval(wordAnimationTimer);

    let wordIdx = 0;
    function renderWord() {
      if (!isPlaying) return;
      captionText.textContent = words[wordIdx];
      captionText.classList.remove('word-highlight');

      // Add highlight to key words
      if (wordIdx % 2 === 1 || wordIdx === words.length - 1) {
        captionText.classList.add('word-highlight');
      }

      wordIdx = (wordIdx + 1) % words.length;
    }

    renderWord();
    wordAnimationTimer = setInterval(renderWord, 550);
  }

  // Toggle Play / Pause Live Demo
  togglePlayBtn.addEventListener('click', () => {
    isPlaying = !isPlaying;
    if (isPlaying) {
      togglePlayBtn.textContent = 'Pause Demo';
      startCaptionAnimation(activeData.clips[currentClipIndex].words);
    } else {
      togglePlayBtn.textContent = 'Resume Demo';
    }
  });

  // Caption Style Change (Glossy Black + Light Green)
  captionStyleSelect.addEventListener('change', (e) => {
    const style = e.target.value;
    captionText.className = 'caption-word';

    if (style === 'neon-glow') {
      captionText.style.background = '#000';
      captionText.style.color = '#00ff87';
      captionText.style.border = '2px solid #00ff87';
      captionText.style.boxShadow = '0 0 20px rgba(0, 255, 135, 0.4)';
    } else if (style === 'hormozi') {
      captionText.style.background = '#f59e0b';
      captionText.style.color = '#000';
      captionText.style.border = 'none';
      captionText.style.boxShadow = '0 5px 25px rgba(245, 158, 11, 0.5)';
    } else if (style === 'cyber-yellow') {
      captionText.style.background = '#00ffaa';
      captionText.style.color = '#000';
      captionText.style.border = '2px solid #fff';
      captionText.style.boxShadow = '0 0 25px rgba(0, 255, 170, 0.6)';
    } else if (style === 'minimal') {
      captionText.style.background = 'rgba(0,0,0,0.8)';
      captionText.style.color = '#fff';
      captionText.style.border = 'none';
      captionText.style.boxShadow = 'none';
    }
  });

  // Export / Download Action
  exportBtn.addEventListener('click', () => {
    const clip = activeData.clips[currentClipIndex];
    alert(`🎉 Downloading clip: "${clip.title}"\nFormat: 1080x1920 MP4 (60 FPS)\nIncludes: Burned-in subtitles & video-matched caption file.`);
  });

  // Schedule Modal Handling
  function openScheduleModal(clipIdx) {
    const clip = activeData.clips[clipIdx];
    modalClipTitle.value = clip.title.replace(/"/g, '');
    modalClipCaption.value = clip.autoCaption;

    // Render Trending Pills
    trendingPillsPreview.innerHTML = clip.hashtagsList.map(h => `<span class="trending-pill-chip">${h}</span>`).join('');

    scheduleModal.classList.add('open');
  }

  function closeScheduleModal() {
    scheduleModal.classList.remove('open');
  }

  modalCloseBtn.addEventListener('click', closeScheduleModal);
  modalCancelBtn.addEventListener('click', closeScheduleModal);
  scheduleModal.addEventListener('click', (e) => {
    if (e.target === scheduleModal) closeScheduleModal();
  });

  // Open from preview phone button
  modalTriggerBtn.addEventListener('click', () => {
    openScheduleModal(currentClipIndex);
  });

  // Open from clip card mini buttons
  document.querySelectorAll('.open-schedule-modal-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const idx = parseInt(btn.dataset.clipIdx, 10);
      selectClip(idx);
      openScheduleModal(idx);
    });
  });

  // Toggle platform checkboxes in modal
  modalYtBox.addEventListener('click', () => {
    modalYtBox.classList.toggle('selected');
  });
  modalIgBox.addEventListener('click', () => {
    modalIgBox.classList.toggle('selected');
  });

  // Generate / Re-Analyze AI Contextual Hashtags & Caption
  generateHashtagsBtn.addEventListener('click', () => {
    const clip = activeData.clips[currentClipIndex];
    showToast('Re-analyzing audio transcript with Ollama...', '🧠');

    setTimeout(() => {
      const extraTags = ['#viralvideo', '#explorepage', '#trendingnow', '#fyp', '#dailyshorts', '#algorithmhack'];
      const combined = [...clip.hashtagsList, extraTags[Math.floor(Math.random() * extraTags.length)]];
      modalClipCaption.value = `[AI Transcript Match] ${clip.title.replace(/"/g, '')} 🔥\n\n${clip.hook}\nDrop your reaction in comments! 👇\n\n${combined.join(' ')}`;
      trendingPillsPreview.innerHTML = combined.map(h => `<span class="trending-pill-chip">${h}</span>`).join('');
      showToast('Contextual caption & trending hashtags refreshed!', '✨');
    }, 400);
  });

  // Confirm Schedule Action
  confirmScheduleBtn.addEventListener('click', () => {
    const title = modalClipTitle.value;
    const caption = modalClipCaption.value;
    const date = document.getElementById('schedule-date').value;
    const time = document.getElementById('schedule-time').value;

    const isYt = modalYtBox.classList.contains('selected');
    const isIg = modalIgBox.classList.contains('selected');

    if (!isYt && !isIg) {
      alert('Please select at least one platform (YouTube or Instagram)!');
      return;
    }

    // Create New Queue Card
    const newCard = document.createElement('div');
    newCard.className = 'queue-card';
    newCard.innerHTML = `
      <div class="queue-top">
        <div class="target-platforms">
          ${isYt ? '<span class="platform-pill pill-yt">▶ YouTube Shorts</span>' : ''}
          ${isIg ? '<span class="platform-pill pill-ig">📸 Reels</span>' : ''}
        </div>
        <span class="queue-time">${date} at ${time}</span>
      </div>
      <h4 class="queue-title">"${title}"</h4>
      <p class="queue-caption">${caption.slice(0, 140)}...</p>
      <div class="queue-footer">
        <span class="queue-status-badge">⏳ Auto-Post Scheduled</span>
        <span>AI Context & Trending Tags Injected</span>
      </div>
    `;

    queueGrid.prepend(newCard);
    closeScheduleModal();
    showToast(`Clip scheduled with video-tailored hashtags & caption on ${date} at ${time}!`, '🚀');

    // Smooth scroll to scheduler
    document.getElementById('scheduler-section').scrollIntoView({ behavior: 'smooth' });
  });

  // Initialize
  startCaptionAnimation(activeData.clips[0].words);
});

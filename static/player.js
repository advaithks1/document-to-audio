window.onload = async function () {
    const audio = document.getElementById("audioPlayer");
    const progressBar = document.getElementById("progressBar");
    const playPauseBtn = document.getElementById("playPauseBtn");
    const activeSentence = document.getElementById("activeSentence");

    let transcript = await fetch('/transcript').then(res => res.json());

    function togglePlay() {
        if (audio.paused) {
            audio.play();
            playPauseBtn.textContent = "⏸️";
        } else {
            audio.pause();
            playPauseBtn.textContent = "▶️";
        }
    }

    audio.addEventListener('timeupdate', () => {
        if (audio.duration) {
            progressBar.value = (audio.currentTime / audio.duration) * 100;
        }

        transcript.forEach((t) => {
            if (audio.currentTime >= t.start && audio.currentTime < (t.start + t.duration)) {
                activeSentence.textContent = t.sentence;
            }
        });
    });

    progressBar.addEventListener('input', () => {
        audio.currentTime = (progressBar.value / 100) * audio.duration;
    });

    window.togglePlay = togglePlay;
}

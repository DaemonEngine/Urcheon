# This file allows building and running the software with the Nix package
# manager, used in NixOS or on another distribution.

{
  description = "a toolset to manage and build `pk3` or `dpk` source directories";

  inputs = {
    nixpkgs.url = "flake:nixpkgs";

    crunch.url = "github:DaemonEngine/crunch";
    crunch.inputs.nixpkgs.follows = "nixpkgs";

    netradiant.url = "gitlab:xonotic/netradiant";
    netradiant.inputs.nixpkgs.follows = "nixpkgs";

    sloth.url = "github:Unvanquished/Sloth";
    sloth.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, crunch, netradiant, sloth }:
    let
      lib = nixpkgs.legacyPackages.x86_64-linux.lib;
    in {

      packages = lib.mapAttrs (system: pkgs: {
        iqmtool =
          pkgs.stdenv.mkDerivation {
            name = "iqmtool";
            src = pkgs.fetchsvn {
              url = "http://svn.code.sf.net/p/fteqw/code/trunk/iqm/";
              rev = 6258;
              sha256 = "sha256-ddRG4waOSDNfw0OlAnQAFRfdF4caXVefVZWXAvUaszQ=";
            };

            buildInputs = with pkgs; [
              gcc gnumake
            ];

            installPhase = ''
              if [ -f iqmtool ]; then
                install -Dm0755 iqmtool -T $out/bin/iqmtool
              else
                install -Dm0755 iqm -T $out/bin/iqmtool
              fi
            '';
          };

        urcheon = pkgs.python3.pkgs.buildPythonPackage {
          name = "urcheon";

          src = pkgs.lib.cleanSource ./.;

          format = "other";

          buildInputs = [
            (pkgs.python3.withPackages
              (ps: [ ps.colorama ps.psutil ps.toml ps.pillow ]))
          ];

          propagatedBuildInputs = with pkgs; [
            netradiant.packages."${system}".quake-tools
            crunch.defaultPackage."${system}"
            sloth.defaultPackage."${system}"
            opusTools
            libwebp
          ];

          installPhase = ''
            runHook preInstall

            mkdir $out/
            cp -ra bin/ profile/ Urcheon/ $out/

            runHook postInstall
          '';
        };

        crunch = crunch.defaultPackage."${system}";
        sloth = sloth.defaultPackage."${system}";
      } // netradiant.packages."${system}") nixpkgs.legacyPackages;

      apps = lib.mapAttrs (system: pkgs: {
        iqmtool = {
          type = "app";
          program = "${self.packages."${system}".iqmtool}/bin/iqmtool";
        };

        urcheon = {
          type = "app";
          program = "${self.packages."${system}".urcheon}/bin/urcheon";
        };

        esquirel = {
          type = "app";
          program = "${self.packages."${system}".urcheon}/bin/esquirel";
        };

        crunch = crunch.defaultApp."${system}";
        sloth = sloth.defaultApp."${system}";
      }) nixpkgs.legacyPackages;

    };
}
